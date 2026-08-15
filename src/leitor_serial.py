"""
Leitor serial para o protocolo binario do teste_ads1256_serial.ino

Framing de cada pacote:
    [0xAA][0x55][N][ N * 9 bytes de amostras ][checksum XOR]

Cada amostra (9 bytes, little-endian):
    uint32_t indice
    uint8_t  canal
    float    tensao

IMPORTANTE: o baud rate aqui DEVE ser o mesmo configurado no Serial.begin()
do .ino. Com DRATE_30000SPS o throughput efetivo ciclando 8 canais e de
~4374 amostras/s (~39 kB/s com o overhead do protocolo), o que excede o
que 115200 baud consegue escoar (~11.5 kB/s). Por isso o baud foi elevado
para 921600 -- lembre-se de atualizar o Serial.begin() no .ino tambem.

Requer: pip install pyserial
"""

import struct
import time
import serial
from pathlib import Path

PORTA = "COM8"
BAUD = 921600  # deve ser IGUAL ao Serial.begin() no .ino

SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55

FORMATO_AMOSTRA = "<IBf"          # uint32, uint8, float -> 9 bytes
TAM_AMOSTRA = struct.calcsize(FORMATO_AMOSTRA)

valor_sps = "30000SPS"
N_CHANNELS = 8
N_SAMPLES_PER_CHANNEL = 10000
AMOSTRAS_POR_ARQUIVO = N_CHANNELS * N_SAMPLES_PER_CHANNEL  # 80000, igual ao TOTAL_SAMPLES do .ino

N_ARQUIVOS = 5
PROGRESSO_A_CADA = 2000  # imprime status no console a cada N amostras (em vez de a cada 1)


SENTINELA = b"READY_BINARY_STREAM"
FINALIZADO = b"END_OF_REPORT"


def conectar_serial(porta: str, baud: int, intervalo_s: float = 1.0) -> serial.Serial:
    """
    Tenta abrir a porta serial repetidamente ate ter sucesso. Permite deixar
    o script em "standby" antes mesmo do ESP32 estar conectado/ligado.
    """
    tentativa = 0
    while True:
        tentativa += 1
        try:
            ser = serial.Serial(porta, baud, timeout=1)
            print(f"Conectado em {porta} @ {baud} bps")
            return ser
        except serial.SerialException:
            print(f"  Aguardando dispositivo em {porta}...", end="\r")
            time.sleep(intervalo_s)


def ler_serial(ser: serial.Serial):
    """
    Le e imprime linhas de texto (boot do ESP32 + mensagens de depuracao do
    setup()) ate encontrar a linha sentinela.
    """
    buffer = b""
    while True:
        byte = ser.read(1)
        if not byte:
            continue  # timeout

        buffer += byte
        if byte == b"\n":
            linha = buffer.strip()
            if linha:
                print(f"  [ESP32] {linha.decode(errors='replace')}")
            if linha == SENTINELA:
                print("Sentinela recebida -- iniciando leitura binaria.\n")
                return
            if linha == FINALIZADO:
                print("Iniciando nova coleta...")
                return
            buffer = b""


def ler_pacote(ser: serial.Serial):
    """
    Le e decodifica um unico pacote. Retorna:
      - lista de tuplas (indice, canal, tensao) em caso de sucesso
      - [] (lista vazia) se nao havia dados disponiveis (timeout simples,
        esperado durante as pausas do ESP32 entre rajadas) - NAO e um erro
      - None se houve uma falha real de protocolo (sync perdido apos dados
        comecarem a chegar, pacote incompleto ou checksum invalido)
    """
 
    # Primeiro byte: se der timeout aqui, e apenas silencio do ESP32
    # (ex: durante o vTaskDelay entre rajadas) - nao conta como erro.
    b = ser.read(1)
    if not b:
        return []
    if b[0] != SYNC_BYTE_1:
        return None  # byte de lixo em meio ao fluxo -- erro real de sync
 
    b = ser.read(1)
    if not b or b[0] != SYNC_BYTE_2:
        return None
 
    n_bytes = ser.read(1)
    if not n_bytes:
        return None
    n = n_bytes[0]
 
    payload = ser.read(n * TAM_AMOSTRA)
    if len(payload) != n * TAM_AMOSTRA:
        return None
 
    checksum_lido = ser.read(1)
    if not checksum_lido:
        return None
 
    checksum_calc = 0
    for byte in payload:
        checksum_calc ^= byte
 
    if checksum_calc != checksum_lido[0]:
        print("Checksum invalido, pacote descartado.")
        return None
 
    amostras = []
    for i in range(n):
        trecho = payload[i * TAM_AMOSTRA:(i + 1) * TAM_AMOSTRA]
        indice, canal, tensao = struct.unpack(FORMATO_AMOSTRA, trecho)
        amostras.append((indice, canal, tensao))
 
    return amostras


def main():
    print("Script em standby - aguardando o ESP32 ficar disponivel na porta "
          f"{PORTA}. Pode ligar/conectar o ESP32 a qualquer momento.")

    dir_path = Path(f"rodada2/{valor_sps}")

    dir_path.mkdir(parents=True, exist_ok=True)

    ser = conectar_serial(PORTA, BAUD)
    with ser:
        ser.reset_input_buffer()

        # Consome o banner de boot do ESP32 e os prints de depuracao do
        # setup(), sem contá-los como erros, ate a sentinela de "pronto"
        print("Aguardando ESP32 inicializar...")
        ler_serial(ser)

        for i in range(N_ARQUIVOS):
            nome_arquivo = f"{dir_path}\\coleta{i}_{valor_sps}.csv"
            print(f"\n=== Iniciando coleta {i} -> {nome_arquivo} "
                  f"({AMOSTRAS_POR_ARQUIVO} amostras esperadas) ===")

            with open(nome_arquivo, "w", newline="") as arquivo:
                arquivo.write("indice,canal,tensao\n")

                total_amostras = 0
                pacotes_com_erro = 0
                buffer_linhas = []

                while total_amostras < AMOSTRAS_POR_ARQUIVO:
                    amostras = ler_pacote(ser)
                    if amostras is None:
                        pacotes_com_erro += 1
                        continue

                    for indice, canal, tensao in amostras:
                        buffer_linhas.append(f"{indice},{canal},{tensao:.6f}\n")
                        total_amostras += 1

                        if total_amostras % PROGRESSO_A_CADA == 0:
                            print(f"  {total_amostras}/{AMOSTRAS_POR_ARQUIVO} amostras "
                                  f"(erros de pacote: {pacotes_com_erro})     ",
                                  end="\r", flush=True)

                    # Escreve em lote (mais eficiente que linha a linha)
                    arquivo.writelines(buffer_linhas)
                    buffer_linhas.clear()
                    arquivo.flush()

            print()
            
            print(f"Amostras salvas em {nome_arquivo} -- (pacotes com erro/descartados: {pacotes_com_erro})")
            
            ler_serial(ser)
            

if __name__ == "__main__":
    main()