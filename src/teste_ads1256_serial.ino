#include <ADS1256.h>
#include <SPI.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

// =============================
// Definição de Pinos SPI para o ADS1256
// =============================

#if defined(ARDUINO_ARCH_ESP32)
#pragma message "Using ESP32"
SPIClass hspi(HSPI);
//#define USE_HSPI  // Uncomment to use HSPI instead of VSPI
#if defined(USE_HSPI)
#pragma message "Using HSPI"
#define USE_SPI hspi
#else
#pragma message "Using VSPI"
#define USE_SPI SPI
#endif
//-----------------------------------------
#else  //Default fallback (Arduino AVR)
#define SPI_MOSI MOSI
#define SPI_MISO MISO
#define SPI_SCK SCK
#define USE_SPI SPI
//-----------------------------------------
#endif

// Pinos Utilizados no ESP32
#define PIN_CS_ADS      5
#define PIN_DRDY        17
#define PIN_RESET       25

#define SCK             18
#define MISO            19
#define MOSI            23

#define ADS_VREF        2.500f

ADS1256 A(PIN_DRDY, PIN_RESET, ADS1256::PIN_UNUSED, PIN_CS_ADS, ADS_VREF, &USE_SPI);
// DRDY, RESET, SYNC(PDWN), CS, VREF(float) - ESP32 WROOM 32 - OK (HSPI+VSPI)

int pgaValues[7] = { PGA_1, PGA_2, PGA_4, PGA_8, PGA_16, PGA_32, PGA_64 };  // Array com os valores de PGA
int pgaSelection = 0;                                                       // Índice do PGA escolhido

int drateValues[16] = {
  DRATE_30000SPS,   // 0
  DRATE_15000SPS,   // 1
  DRATE_7500SPS,    // 2
  DRATE_3750SPS,    // 3
  DRATE_2000SPS,    // 4
  DRATE_1000SPS,    // 5
  DRATE_500SPS,     // 6
  DRATE_100SPS,     // 7
  DRATE_60SPS,      // 8
  DRATE_50SPS,      // 9
  DRATE_30SPS,      // 10
  DRATE_25SPS,      // 11
  DRATE_15SPS,      // 12
  DRATE_10SPS,      // 13
  DRATE_5SPS,       // 14
  DRATE_2SPS        // 15
};  // Array com as taxas de amostragem

int drateSelection = 5;  // Índice da taxa de amostragem escolhida (0 = 30000 SPS)

// =============================
// Parâmetros da coleta
// cycleSingle() sempre percorre os 8 canais single-ended em sequência
// (SING_0..SING_7), então o número de canais é fixo.
// =============================

#define N_CHANNELS              8
#define N_SAMPLES_PER_CHANNEL   10000
#define TOTAL_SAMPLES           (N_CHANNELS * N_SAMPLES_PER_CHANNEL)  // 80000

// =============================
// Estrutura do pacote de amostra
// (packed -> sem padding, 9 bytes por amostra: 4+1+4)
// =============================

typedef struct __attribute__((packed)) {
    uint32_t indice;
    uint8_t  canal;
    float    tensao;
} AmostraADS;

// Relatorio de fim de burst -- enviado por uma fila separada da de amostras,
// para que APENAS a taskSerialSend escreva na Serial (ver explicacao abaixo).
typedef struct {
    uint32_t num_coleta;
    int      drate_value;
    long     tempo_ms;
} RelatorioColeta;

// =============================
// FreeRTOS
// =============================

#define QUEUE_LENGTH        512     // nº máx. de amostras pendentes na fila
#define BATCH_SIZE          40      // nº de amostras agrupadas por pacote serial
#define BATCH_TIMEOUT_MS    100     // tempo máx. de espera p/ fechar um pacote parcial

QueueHandle_t filaAmostras;
QueueHandle_t filaRelatorios;

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
    uint32_t num_coleta = 0;
    AmostraADS amostra;
    long startTime;
    long endTime = 0;

    while (true) {
        // cycleSingle() sempre cicla pelos 8 canais na ordem SING_0..SING_7
        startTime = millis();

        for (uint32_t i = 0; i < TOTAL_SAMPLES; i++) {
            amostra.tensao = A.convertToVoltage(A.cycleSingle());
            amostra.canal  = (uint8_t)(i % N_CHANNELS);
            amostra.indice = indiceGlobal++;

            // Envia para a fila; se a fila estiver cheia por mais de 10 ms,
            // a amostra é descartada (evita travar a task de aquisição)
            if (xQueueSend(filaAmostras, &amostra, pdMS_TO_TICKS(10)) != pdPASS) {
                // Opcional: contabilizar/depurar amostras perdidas aqui
            }

            // Cede o processador periodicamente para alimentar o watchdog
            if ((i & 0x3F) == 0) {  // a cada 64 iterações
                vTaskDelay(1);
            }
        }

        A.stopConversion();

        endTime = millis() - startTime;     // Calcula tempo de execução

        RelatorioColeta rel;
        rel.num_coleta  = num_coleta;
        rel.tempo_ms    = endTime;
        xQueueSend(filaRelatorios, &rel, portMAX_DELAY);

        indiceGlobal = 0;
        num_coleta++;

        // Aguarda antes de iniciar a próxima coleta de 10000 amostras/canal
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

    while (true) {
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

        // Verificacao de relatorio pendente
        if (count == 0) {
            RelatorioColeta rel;
            if (xQueueReceive(filaRelatorios, &rel, 0) == pdPASS) {
                Serial.print("Coleta ");
                Serial.print(rel.num_coleta);
                Serial.print("Tempo: ");
                Serial.print(rel.tempo_ms);
                Serial.println(" ms");
                Serial.print("Amostragem media: ");
                Serial.print(80000 / (rel.tempo_ms * 0.001));
                Serial.println(" SPS")
                Serial.println("END_OF_REPORT");
            }
        }
    }
}

void setup() {
    Serial.begin(921600);

    while (!Serial) {
        ;   // Aguarda a serial ficar disponível
    }

    Serial.println("ADS1256 - Coleta de Dados (8 canais, pacote binario)");

#if defined(USE_HSPI)
    hspi.begin(14, 25, 13);
#endif

    // Inicialização do ADS1256 e definição de DRATE
    A.InitializeADC();
    A.setDRATE(drateValues[drateSelection]);

    uint8_t status = (uint8_t)A.readRegister(STATUS_REG);
    Serial.print("STATUS ADS1256: ");
    Serial.println(status, BIN);
    Serial.println("ADS1256 inicializado.");

    // Cria a fila de amostras
    filaAmostras = xQueueCreate(QUEUE_LENGTH, sizeof(AmostraADS));

    if (filaAmostras == NULL) {
        Serial.println("Erro ao criar a fila de amostras!");
        while (true);
    }

    // Fila de relatorios de fim de burst (pequena, so precisa de poucos slots)
    filaRelatorios = xQueueCreate(4, sizeof(RelatorioColeta));

    if (filaRelatorios == NULL) {
        Serial.println("Erro ao criar a fila de relatorios!");
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

    Serial.println("Tasks criadas.");

    // Sentinela: marca o fim de todo o texto de depuracao. A partir daqui,
    // NENHUM outro Serial.print/println deve ser usado - só o protocolo binario.
    // O script Python espera por esta linha exata antes de comecar a interpretar
    // os bytes recebidos como pacotes binarios.
    Serial.println("READY_BINARY_STREAM");
}

void loop() {}
