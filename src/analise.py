import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# ======================================================
# Funções Auxiliares
# ======================================================

def carregar_dados(file) -> pd.DataFrame:
    """Carrega o arquivo de dados."""
    try:
        df_total = pd.read_csv(
            file
        )
        if df_total.shape[1] < 3:
            raise ValueError
    except Exception:
        st.error("Arquivo inválido.")
        st.stop()
    
    df_total["indice"] = df_total["indice"].astype(int)
    df_total["canal"] = df_total["canal"].astype(int)
    df_total["tensao"] = df_total["tensao"].astype(float)    

    dados_por_canal = {
        canal: grupo.reset_index(drop=True)
        for canal, grupo in df_total.groupby("canal")
    }

    return df_total, dados_por_canal


def carregar_multiplos_arquivos(arquivos: dict) -> pd.DataFrame:
    """
    Carrega vários arquivos de coleta (ex.: taxas de amostragem diferentes)
    e retorna um único DataFrame concatenado, com uma coluna extra 'fonte'
    identificando de qual arquivo/amostragem cada linha veio.

    Parâmetros
    ----------
    arquivos : dict
        Dicionário no formato {rotulo: arquivo}, onde 'rotulo' é o texto
        que identifica a coleta (ex.: "500 SPS", "1000 SPS") e 'arquivo'
        é o caminho ou o buffer (ex.: retornado pelo st.file_uploader).

    Retorna
    -------
    pd.DataFrame
        DataFrame único com todas as coletas, contendo a coluna 'fonte'.
    """
    dfs = []

    for rotulo, arquivo in arquivos.items():
        df_total, _ = carregar_dados(arquivo)
        df_total["fonte"] = rotulo
        dfs.append(df_total)

    if not dfs:
        raise ValueError("Nenhum arquivo foi fornecido para carregamento.")

    return pd.concat(dfs, ignore_index=True)


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
    canal = df["canal"].unique()
    
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


def plotar_comparacao_amostragem(
    df_comparacao: pd.DataFrame,
    canal: int,
    tensao_esperada: float = None,
    eixo_x: str = "indice",
):
    """
    Gera um gráfico de linhas comparando, para um único canal, o sinal de
    várias coletas (ex.: taxas de amostragem diferentes), cada uma com
    uma cor diferente. Espera um DataFrame gerado por
    `carregar_multiplos_arquivos`, que possui a coluna 'fonte'.

    Parâmetros
    ----------
    df_comparacao : pd.DataFrame
        DataFrame concatenado (com a coluna 'fonte') de várias coletas.
    canal : int
        Canal a ser exibido no gráfico.
    tensao_esperada : float, opcional
        Se informado, desenha uma linha horizontal tracejada de referência.
    eixo_x : str
        Coluna a ser usada no eixo X. Use "indice" para comparar amostra a
        amostra, ou "tempo" caso exista uma coluna de tempo normalizado.

    Retorna
    -------
    plotly.graph_objects.Figure
    """
    if "fonte" not in df_comparacao.columns:
        raise ValueError(
            "O DataFrame não possui a coluna 'fonte'. "
            "Utilize carregar_multiplos_arquivos() para gerá-lo."
        )

    df_filtrado = df_comparacao[df_comparacao["canal"] == canal].copy()

    if df_filtrado.empty:
        raise ValueError(f"Nenhum dado encontrado para o canal {canal}.")

    df_filtrado["fonte"] = df_filtrado["fonte"].astype(str)

    fig = px.line(
        df_filtrado,
        x=eixo_x,
        y="tensao",
        color="fonte",
        markers=False,
        title=f"Comparação entre coletas — Canal {canal}",
        labels={
            eixo_x: "Número da amostra" if eixo_x == "indice" else eixo_x,
            "tensao": "Tensão medida (V)",
            "fonte": "Coleta / Amostragem",
        },
    )

    if tensao_esperada is not None:
        fig.add_hline(
            y=tensao_esperada,
            line_dash="dash",
            annotation_text=f"Tensão esperada = {tensao_esperada:.3f} V",
            annotation_position="top left",
        )

    fig.update_layout(
        xaxis_title="Número da amostra" if eixo_x == "indice" else eixo_x,
        yaxis_title="Tensão medida (V)",
        legend_title="Coleta / Amostragem",
        hovermode="x unified",
    )

    return fig


if __name__ == "__main__":
    dados_por_canal = carregar_dados("dados/500SPS/coleta0.csv")
    
    print(dados_por_canal[0].head())