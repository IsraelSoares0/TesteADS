import pandas as pd
import matplotlib.pyplot as plt

# Caminho arquivo csv
arquivo_csv = "dados/dados_teste_ads1256.csv"

# Leitura do arquivo
df = pd.read_csv(arquivo_csv)

print(df.head())

# Ordena os dados por SPS
df = df.sort_values(by="Quantidade de Amostras por segundo (SPS)")

# Cria figura
plt.figure(figsize=(10, 6))

for canal in df["Canal"].unique():
    dados_canal = df[df["Canal"] == canal]
    
    plt.plot(
        dados_canal["Quantidade de Amostras por segundo (SPS)"],
        dados_canal["Tensão Média"],
        marker = "o",
        label = canal
    )

plt.axhline(y=1.65, color='r', linestyle='--', label='Valor Esperado')
plt.ylim(1.5, 1.8)
# Configuracao do gráfico
plt.title("Erro Absoluto x SPS - ADS1256")
plt.xlabel("Quantidade de Amostras por segundo (SPS)")
plt.ylabel("Tensão Média (V)")
plt.grid(True)
plt.legend(title="Canal")
plt.tight_layout()

plt.savefig('Grafico.png')