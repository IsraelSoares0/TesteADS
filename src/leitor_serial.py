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
import serial

PORTA = "COM8"
BAUD = 921600  # deve ser IGUAL ao Serial.begin() no .ino

SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55

FORMATO_AMOSTRA = "<IBf"          # uint32, uint8, float -> 9 bytes
TAM_AMOSTRA = struct.calcsize(FORMATO_AMOSTRA)

N_CHANNELS = 8
N_SAMPLES_PER_CHANNEL = 10000
AMOSTRAS_POR_ARQUIVO = N_CHANNELS * N_SAMPLES_PER_CHANNEL  # 80000, igual ao TOTAL_SAMPLES do .ino

N_ARQUIVOS = 5
PROGRESSO_A_CADA = 2000  # imprime status no console a cada N amostras (em vez de a cada 1)


def ler_pacote(ser: serial.Serial):
    """Le e decodifica um unico pacote. Retorna lista de tuplas (indice, canal, tensao)."""

    # Procura o sincronismo byte a byte
    b = ser.read(1)
    if not b or b[0] != SYNC_BYTE_1:
        return None
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
    with serial.Serial(PORTA, BAUD, timeout=1) as ser:
        print(f"Conectado em {PORTA} @ {BAUD} bps")

        # Descarta qualquer dado antigo/parcial que possa estar no buffer
        ser.reset_input_buffer()

        for i in range(N_ARQUIVOS):
            nome_arquivo = f"coleta{i}.csv"
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
                                  f"(erros de pacote: {pacotes_com_erro})")

                    # Escreve em lote (mais eficiente que linha a linha)
                    arquivo.writelines(buffer_linhas)
                    buffer_linhas.clear()
                    arquivo.flush()

            print(f"Coleta {i} finalizada: {total_amostras} amostras salvas em {nome_arquivo} "
                  f"(pacotes com erro/descartados: {pacotes_com_erro})")


if __name__ == "__main__":
    main()