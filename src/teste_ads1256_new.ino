#include <ADS1256.h>
#include <SPI.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

// =============================
// SPI do ADS1256 (VSPI)
// =============================

SPIClass spiADS(VSPI);

#define ADSvRef         2.5f
#define ADS_SCK         18
#define ADS_MISO        19
#define ADS_MOSI        23
#define PIN_CS_ADS      5

#define PIN_DRDY        17
#define PIN_RESET       25

// =============================
// Configurações do teste
// =============================

#define SPS_CODE            DRATE_2000SPS
#define SPS_VALUE           2000

#define N_CHANNELS          2
#define N_SAMPLES           10000

ADS1256 adc(PIN_DRDY, PIN_RESET, ADS1256::PIN_UNUSED, PIN_CS_ADS, ADSvRef, &spiADS);

// MUX para cada canal em modo single-ended
const uint8_t MUX_CH[8] = {
    SING_0, SING_1, SING_2, SING_3,
    SING_4, SING_5, SING_6, SING_7
};

const char* CH_NAME[8] = {
    "AIN0", "AIN1", "AIN2", "AIN3",
    "AIN4", "AIN5", "AIN6", "AIN7"
};

// =============================
// Estrutura do pacote de amostra
// (packed -> sem padding, 9 bytes por amostra: 4+1+4)
// =============================

typedef struct __attribute__((packed)) {
    uint32_t indice;
    uint8_t  canal;
    float    tensao;
} AmostraADS;

// =============================
// FreeRTOS
// =============================

#define QUEUE_LENGTH        200     // nº máx. de amostras pendentes na fila
#define BATCH_SIZE          20      // nº de amostras agrupadas por pacote serial
#define BATCH_TIMEOUT_MS    100     // tempo máx. de espera p/ fechar um pacote parcial

QueueHandle_t filaAmostras;

TaskHandle_t taskADS_Handle;
TaskHandle_t taskSerial_Handle;

// =============================
// Framing do pacote serial:
// [0xAA][0x55][N][ N * sizeof(AmostraADS) bytes ][checksum XOR]
// =============================

#define SYNC_BYTE_1  0xAA
#define SYNC_BYTE_2  0x55

void enviarPacote(AmostraADS *buffer, uint8_t n) {
    if (n == 0) return;

    uint8_t *bytes = (uint8_t *)buffer;
    size_t totalBytes = (size_t)n * sizeof(AmostraADS);

    uint8_t checksum = 0;
    for (size_t i = 0; i < totalBytes; i++) {
        checksum ^= bytes[i];
    }

    Serial.write(SYNC_BYTE_1);
    Serial.write(SYNC_BYTE_2);
    Serial.write(n);
    Serial.write(bytes, totalBytes);
    Serial.write(checksum);
}

// =============================
// Task ADS1256 - coleta os dados
// Roda no núcleo 1
// =============================

void taskADS1256(void *pvParameters) {
    uint32_t indiceGlobal = 0;

    while(true) {
        // Alterna entre os canais
        for (int i = 0; i < N_SAMPLES; i++) {
            for (int ch = 0; ch < N_CHANNELS; ch++) {
                adc.setMUX(MUX_CH[ch]);
                //adc.readSingle(); // descarta a 1ª leitura (settling do MUX)

                long raw = adc.readSingle();
                float tensao = adc.convertToVoltage(raw);

                AmostraADS amostra;
                amostra.indice = indiceGlobal++;
                amostra.canal  = (uint8_t)ch;
                amostra.tensao = tensao;

                // Envia para a fila
                xQueueSend(filaAmostras, &amostra, pdMS_TO_TICKS(20));
            }
        }

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

// =============================
// Task SERIAL - agrupa amostras em lotes e envia
// Roda no núcleo 0
// =============================

void taskSerialSend(void *pvParameters) {
    static AmostraADS buffer[BATCH_SIZE];
    uint8_t count = 0;
    TickType_t ultimoEnvio = xTaskGetTickCount();

    while(true) {
        AmostraADS amostra;

        if (xQueueReceive(filaAmostras, &amostra, pdMS_TO_TICKS(BATCH_TIMEOUT_MS)) == pdPASS) {
            buffer[count++] = amostra;
        }

        bool bufferCheio   = (count >= BATCH_SIZE);
        bool tempoEsgotado = (count > 0) &&
            ((xTaskGetTickCount() - ultimoEnvio) >= pdMS_TO_TICKS(BATCH_TIMEOUT_MS));

        if (bufferCheio || tempoEsgotado) {
            enviarPacote(buffer, count);
            count = 0;
            ultimoEnvio = xTaskGetTickCount();
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_CS_ADS, OUTPUT);
    digitalWrite(PIN_CS_ADS, HIGH);

    Serial.println("Inicializando SPI do ADS1256...");
    spiADS.begin(ADS_SCK, ADS_MISO, ADS_MOSI, PIN_CS_ADS);
    delay(100);

    Serial.println("Inicializando ADS1256...");
    adc.InitializeADC();
    adc.setDRATE(SPS_CODE);

    uint8_t status = (uint8_t)adc.readRegister(STATUS_REG);
    Serial.print("STATUS ADS1256: ");
    Serial.println(status, BIN);
    Serial.println("ADS1256 inicializado.");

    // Cria a fila de amostras

    filaAmostras = xQueueCreate(QUEUE_LENGTH, sizeof(AmostraADS));

    if (filaAmostras == NULL) {
        Serial.println("Erro ao criar a fila de amostras!");
        while (true);
    }

    Serial.println("Iniciando tasks FreeRTOS...");

    xTaskCreatePinnedToCore(
        taskADS1256,
        "TaskADS1256",
        4096,
        NULL,
        2,                  // prioridade mais alta
        &taskADS_Handle,
        1                   // núcleo 1
    );

    xTaskCreatePinnedToCore(
        taskSerialSend,
        "TaskSerial",
        4096,
        NULL,
        1,                  // prioridade menor
        &taskSerial_Handle,
        0                   // núcleo 0
    );

    Serial.println("Tasks criadas. Streaming binario iniciado (pare o monitor serie de texto).");
}

void loop() {}
