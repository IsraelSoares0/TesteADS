"""
Leitor serial de exemplo para o protocolo binario do teste_ads1256_serial.ino

Framing de cada pacote:
    [0xAA][0x55][N][ N * 9 bytes de amostras ][checksum XOR]

Cada amostra (9 bytes, little-endian):
    uint32_t indice
    uint8_t  canal
    float    tensao

Requer: pip install pyserial
"""

import struct
import serial

PORTA = "COM8"
BAUD = 115200

SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55

FORMATO_AMOSTRA = "<IBf"          # uint32, uint8, float -> 9 bytes
TAM_AMOSTRA = struct.calcsize(FORMATO_AMOSTRA)


def ler_pacote(ser: serial.Serial):
    """Le e decodifica um unico pacote. Retorna lista de tuplas (indice, canal, tensao)."""

    # Procura o sincronismo
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

        with open("coleta.csv", "w") as arquivo:
            arquivo.write("indice,canal,tensao\n")

            while True:
                amostras = ler_pacote(ser)
                if amostras is None:
                    continue

                for indice, canal, tensao in amostras:
                    linha = f"{indice},{canal},{tensao:.6f}"
                    arquivo.write(linha + "\n")
                    print(linha)

                arquivo.flush()


if __name__ == "__main__":
    main()
