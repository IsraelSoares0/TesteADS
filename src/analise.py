import pandas as pd
import numpy as np
import streamlit as st

# ======================================================
# Funções Auxiliares
# ======================================================

def carregar_dados(file) -> pd.DataFrame:
    """Carrega o arquivo de dados."""
    try:
        df_total = pd.read_csv(
            file,
            header=None,
            names=["amostra", "tensao", "ch"]
        )
        if df_total.shape[1] < 3:
            raise ValueError
    except Exception:
        st.error("Arquivo inválido.")
        st.stop()
    
    df_total["amostra"] = df_total["amostra"].astype(int)
    df_total["tensao"] = df_total["tensao"].astype(float)
    df_total["ch"] = df_total["ch"].astype(int)    

    dados_por_canal = {
        canal: grupo.reset_index(drop=True)
        for canal, grupo in df_total.groupby("ch")
    }

    return df_total, dados_por_canal


def obter_estatisticas(df: pd.DataFrame, tensao_esperada: float) -> dict:
    """
    Calcula estatísticas do teste
    
    A função adiciona ao DataFrame as colunas:
    - erro
    - erro_percentual
    
    E retorna um dicionario com estatiticas gerais
    """
    
    if "tensao" not in df.columns:
        raise ValueError("Dataframe não contém coluna 'tensao'.")
    if tensao_esperada == 0:
        raise ValueError("A tensão esperada não pode ser igual a zero.")
    
    df["tensao"] = pd.to_numeric(df["tensao"], errors="coerce")
    
    tensoes = df["tensao"].dropna()
    
    if tensoes.empty:
        raise ValueError("A coluna 'tensao' não possui valores numéricos válidos.")

    # Dados de erro
    
    df["erro"] = np.abs(df["tensao"] - tensao_esperada)
    df["erro_percentual"] = (np.abs(df["erro"] / tensao_esperada)) * 100
    
    # Estatisticas Gerais
    
    media = tensoes.mean()
    erro_absoluto = np.abs(media - tensao_esperada)
    erro_percentual = (erro_absoluto / tensao_esperada) * 100
    
    desvio_padrao = tensoes.std()
    minimo = tensoes.min()
    maximo = tensoes.max()
    
    ruido = maximo - minimo
    canal = df["ch"].unique()
    
    estatisticas = {
        "canal": canal,
        "tensao_esperada": tensao_esperada,
        "media": media,
        "erro_absoluto": erro_absoluto,
        "erro_percentual": erro_percentual,
        "desvio_padrao": desvio_padrao,
        "minimo": minimo,
        "maximo": maximo,
        "ruido": ruido,
        "quantidade_amostras": len(tensoes),
    }
    
    return estatisticas

def obter_estatisticas_por_canal(dados_por_canal: dict, tensao_esperada: float) -> dict:
    estatisticas = {}

    for canal, df_canal in dados_por_canal.items():
        stats = obter_estatisticas(df_canal, tensao_esperada)

        estatisticas[canal] = stats

    return estatisticas


if __name__ == "__main__":
    dados_por_canal = carregar_dados("dados/coleta_teste.csv")
    
    estatisticas = obter_estatisticas_por_canal(dados_por_canal, 1.650)
    
    print(dados_por_canal[0].head())