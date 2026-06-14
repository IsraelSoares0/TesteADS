#include <ADS1256.h>
#include <math.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// Pinos ADS1256
#define ADSvRef         2.5f
#define PIN_DRDY        17
#define PIN_RESET       2
#define PIN_CS          5
// Amostras por segundo
#define VALIDATION_SECONDS  3
#define SPS                 DRATE_30000SPS
#define N_SAMPLES           (VALIDATION_SECONDS * 30000)

// SPS Rates
/*
#define DRATE_30000SPS 0b11110000 //240
#define DRATE_15000SPS 0b11100000 //224
#define DRATE_7500SPS 0b11010000  //208
#define DRATE_3750SPS 0b11000000  //192
#define DRATE_2000SPS 0b10110000  //176
#define DRATE_1000SPS 0b10100001  //161
#define DRATE_500SPS 0b10010010   //146
#define DRATE_100SPS 0b10000010   //130
#define DRATE_60SPS 0b01110010    //114
#define DRATE_50SPS 0b01100011    //99
#define DRATE_30SPS 0b01010011    //83
#define DRATE_25SPS 0b01000011    //67
#define DRATE_15SPS 0b00110011    //51
#define DRATE_10SPS 0b00100011    //35
#define DRATE_5SPS 0b00010011     //19
#define DRATE_2SPS 0b00000011     //3
*/

// Construct ADS1256
ADS1256 adc(PIN_DRDY, PIN_RESET, ADS1256::PIN_UNUSED, PIN_CS, ADSvRef, &SPI); 

// Tensão esperada: deve ser ajustada com o valor medido pelo multímetro
// N_SAMPLES deve ser modificado para equivaler a 5 * SPS.
#define V_EXPECTED      1.650f
#define N_CHANNELS      2

struct ChannelResult {
    float mean;
    float stddev;
    float min_v;
    float max_v;
    float error_abs;
    float error_pct;
    float noise_pp;
};

struct ValidationResult {
    ChannelResult ch[N_CHANNELS];
};

// Queue de resultados
QueueHandle_t resultQueue;

// Mux para cada canal em modo single-ended
const uint8_t MUX_CH[8] = {
    SING_0, SING_1, SING_2, SING_3,
    SING_4, SING_5, SING_6, SING_7
};

const char* CH_NAME[8] = {
    "AIN0", "AIN1", "AIN2", "AIN3",
    "AIN4", "AIN5", "AIN6", "AIN7"
};

void tValidate(void *_) {
    while (true) {
        ValidationResult result;

        for (int ch = 0; ch < N_CHANNELS; ch++) {
            adc.setMUX(MUX_CH[ch]);

            float mean = 0.0f;
            float m2 = 0.0f;
            float min_v = 0.0f;
            float max_v = 0.0f;

            for (int i = 0; i < N_SAMPLES; i++) {
                long raw = adc.readSingle();
                float value = adc.convertToVoltage(raw);

                if (i == 0) {
                    mean = value;
                    min_v = value;
                    max_v = value;
                    m2 = 0.0f;
                } else {
                    float delta = value - mean;
                    mean += delta / (i + 1);
                    float delta2 = value - mean;
                    m2 += delta * delta2;

                    if (value < min_v) min_v = value;
                    if (value > max_v) max_v = value;
                }
            }

            float variance = m2 / (N_SAMPLES - 1);
            float stddev = sqrtf(variance);
 
            result.ch[ch] = {
                .mean      = mean,
                .stddev    = stddev,
                .min_v     = min_v,
                .max_v     = max_v,
                .error_abs = mean - V_EXPECTED,
                .error_pct = ((mean - V_EXPECTED) / V_EXPECTED) * 100.0f,
                .noise_pp  = max_v - min_v
            };
        }

        xQueueSend(resultQueue, &result, portMAX_DELAY);

        // Nova validacao a cada 5s
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}


void tReport(void *_) {
    ValidationResult result;
 
    while (true) {
        if (xQueueReceive(resultQueue, &result, portMAX_DELAY)) {
            Serial.println("\n========== VALIDACAO ADS1256 ==========");
            Serial.printf("Amostras        : %d\n",     N_SAMPLES);
            Serial.printf("Tensao esperada : %.6f V\n", V_EXPECTED);
 
            // Imprime resultados de cada canal
            for (int ch = 0; ch < N_CHANNELS; ch++) {
                ChannelResult& r = result.ch[ch];
 
                Serial.printf("\n------- Canal %s -------\n",   CH_NAME[ch]);
                Serial.printf("Tensao medida   : %.6f V\n",     r.mean);
                Serial.printf("Erro            : %+.6f V\n",    r.error_abs);
                Serial.printf("Erro (%)        : %+.4f %%\n",   r.error_pct);
                Serial.printf("Desvio padrao   : %.6f V\n",
                              r.stddev);
                Serial.printf("Ruido pico-pico : %.6f V\n",
                              r.noise_pp);
                Serial.printf("Min / Max       : %.6f V  /  %.6f V\n",
                              r.min_v, r.max_v);
 
                Serial.println("-- Diagnostico --");
 
                if (fabsf(r.error_abs) < 0.050f)
                    Serial.printf("%s - Erro  : OK        (< 50 mV)\n",       CH_NAME[ch]);
                else if (fabsf(r.error_abs) < 0.100f)
                    Serial.printf("%s - Erro  : ATENCAO   (50-100 mV)\n",     CH_NAME[ch]);
                else
                    Serial.printf("%s - Erro  : ERRO      (> 100 mV)\n",      CH_NAME[ch]);
            }
 
            // Comparação entre canais
            Serial.println("\n------- Comparacao entre canais -------");

            float diff_mean = 0.0f;
            int n_pairs = 0;

            for (int i = 0; i < N_CHANNELS; i++) {
                for (int j = i + 1; j < N_CHANNELS; j++) {
                    diff_mean += fabsf(result.ch[i].mean - result.ch[j].mean);
                    n_pairs++;
                }
            }

            if (n_pairs > 0) {
                diff_mean /= n_pairs;
            } else {
                diff_mean = 0.0f;
            }

            Serial.printf("Diferenca media entre canais : %.6f V  (%.2f LSB)\n",
                        diff_mean, diff_mean / LSB);

            if (diff_mean < 0.001f)
                Serial.println("Canais : OK         (diferenca media < 1 mV)");
            else if (diff_mean < 0.005f)
                Serial.println("Canais : ATENCAO    (diferenca media 1-5 mV)");
            else
                Serial.println("Canais : ERRO       (diferenca media > 5 mV)");
 
            Serial.println("========================================");
        }
    }
}


void setup() {
    Serial.begin(115200);
 
    Serial.println("Inicializando ADS...");
    adc.InitializeADC();
    adc.setDRATE(SPS);   
 
    uint8_t status = (uint8_t)adc.readRegister(STATUS_REG);
    if (status != 0b00110110) {
        Serial.printf("ADC ERROR, status: %d\n", status);
        while (true);
    }
    Serial.printf("ADS OK, status: %d\n", status);
 
    resultQueue = xQueueCreate(5, sizeof(ValidationResult));
    if (resultQueue == NULL) {
        Serial.println("Falha ao criar queue!");
        while (true);
    }
 
    xTaskCreate(tValidate, "Validate", 8192, NULL, 2, NULL);
    xTaskCreate(tReport,   "Report",   4096, NULL, 1, NULL);
 
    Serial.println("Iniciando validacao dos canais AIN0 e AIN1...");
}


void loop() {}