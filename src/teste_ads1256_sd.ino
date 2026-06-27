#include <ADS1256.h>
#include <math.h>
#include <SPI.h>
#include <SD.h>

// =============================
// Criação de objetos SPI diferentes
// =============================


SPIClass spiADS(VSPI);
SPIClass spiSD(HSPI);


// =============================
// ADS1256 - VSPI
// =============================


#define ADSvRef         2.5f
#define ADS_SCK         18
#define ADS_MISO        19
#define ADS_MOSI        23
#define PIN_CS_ADS      5

#define PIN_DRDY        17
#define PIN_RESET       25

// =============================
// SD Card - HSPI
// =============================

#define SD_SCK          14
#define SD_MISO         27
#define SD_MOSI         13
#define PIN_CS_SD       16

// =============================
// Configurações do teste
// =============================

#define VALIDATION_SECONDS  3
#define DEBUG               true

#define SPS_CODE            DRATE_50SPS
#define SPS_VALUE           50

#define N_SAMPLES           (VALIDATION_SECONDS * SPS_VALUE)
#define N_CHANNELS          2

#define V_EXPECTED          1.650f

ADS1256 adc(PIN_DRDY, PIN_RESET, ADS1256::PIN_UNUSED, PIN_CS_ADS, ADSvRef, &spiADS);

// SPS Rates
/*
DRATE_30000SPS 0b11110000 //240
DRATE_15000SPS 0b11100000 //224
DRATE_7500SPS 0b11010000  //208
DRATE_3750SPS 0b11000000  //192
DRATE_2000SPS 0b10110000  //176
DRATE_1000SPS 0b10100001  //161
DRATE_500SPS 0b10010010   //146
DRATE_100SPS 0b10000010   //130
DRATE_60SPS 0b01110010    //114
DRATE_50SPS 0b01100011    //99
DRATE_30SPS 0b01010011    //83
DRATE_25SPS 0b01000011    //67
DRATE_15SPS 0b00110011    //51
DRATE_10SPS 0b00100011    //35
DRATE_5SPS 0b00010011     //19
DRATE_2SPS 0b00000011     //3
*/

// MUX para cada canal em modo single-ended
const uint8_t MUX_CH[8] = {
    SING_0, SING_1, SING_2, SING_3,
    SING_4, SING_5, SING_6, SING_7
};

const char* CH_NAME[8] = {
    "AIN0", "AIN1", "AIN2", "AIN3",
    "AIN4", "AIN5", "AIN6", "AIN7"
};


void realizarColeta(int numero, bool debug) {
    char nomeArquivo[32];

    snprintf(
        nomeArquivo,
        sizeof(nomeArquivo),
        "/coleta_%dSPS_%d.csv",
        SPS_VALUE,
        numero
    );

    Serial.print("Criando arquivo: ");
    Serial.println(nomeArquivo);

    File arquivo = SD.open(nomeArquivo, FILE_APPEND);

    if (!arquivo) {
        Serial.println("Erro ao abrir arquivo no SD.");
        return;
    }

    for (int ch = 0; ch < N_CHANNELS; ch++) {
        adc.setMUX(MUX_CH[ch]);

        adc.readSingle();

        for (int i = 0; i < N_SAMPLES; i++) {
            long raw = adc.readSingle();
            float tensao = adc.convertToVoltage(raw);

            if debug {
                Serial.println(tensao);
            }

            arquivo.print(i);
            arquivo.print(",");
            arquivo.print(tensao, 6);
            arquivo.print(",");
            arquivo.println(ch);
        }
    }

    arquivo.close();

    Serial.println("Coleta finalizada e salva no SD.");
}


void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_CS_ADS, OUTPUT);
    pinMode(PIN_CS_SD, OUTPUT);

    digitalWrite(PIN_CS_ADS, HIGH);
    digitalWrite(PIN_CS_SD, HIGH);

    Serial.println("Inicializando SPI do ADS1256...");
    spiADS.begin(ADS_SCK, ADS_MISO, ADS_MOSI, PIN_CS_ADS);
    delay(100);

    Serial.println("Inicializando SPI do SD card...");
    spiSD.begin(SD_SCK, SD_MISO, SD_MOSI, PIN_CS_SD);
    delay(100);


    // =============================
    // Inicialização do SD Card
    // =============================


    Serial.println("Inicializando SD card...");

    if (!SD.begin(PIN_CS_SD, spiSD)) {
        Serial.println("SD card ERROR");
        while (true);
    }

    Serial.println("SD card OK");


    // =============================
    // Inicialização do ADS1256
    // =============================


    Serial.println("Inicializando ADS1256...");

    digitalWrite(PIN_CS_SD, HIGH);
    digitalWrite(PIN_CS_ADS, HIGH);

    adc.InitializeADC();
    adc.setDRATE(SPS_CODE);

    uint8_t status = (uint8_t)adc.readRegister(STATUS_REG);

    Serial.print("STATUS ADS1256: ");
    Serial.println(status, BIN);

    Serial.println("ADS1256 inicializado.");
    Serial.println("Iniciando teste dos canais...");
}


void loop() {
    static int numeroColeta = 0;

    realizarColeta(numeroColeta, DEBUG);

    numeroColeta++;

    // Nova validação a cada 5 segundos
    delay(5000);
}