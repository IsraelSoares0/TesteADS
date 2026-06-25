import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

import analise as an


# ===============================
# Configuração Geral
# ===============================


st.set_page_config(
    page_title="Dashboard Teste ADS1256",
    layout="wide"
)


# ===============================
# Header
# ===============================


st.html(
    """
    <div style="text-align: center; font-size: x-large">
        <h1>PRD - Análise de Dados</h1>
        <h3><i>Dashboard para Teste ADS1256</i></h3>
    </div>
    """
)

st.divider()

st.html(
    """
    <div style="text-align: justify; text-justify: inter-word">
        <h2 style="font-size: 25px">Introdução</h2>
        <p style="font-size: large">
        Esse Dashboard tem como objetivo receber um arquivo <b>CSV</b> contendo valores de tempo e empuxo obtidos no teste de um ADS1256 utilizando o programa <i>teste_ads1256_sd.ino</i> e gerar um gráfico para análise utilizando <i>numpy, streamlit e plotly</i>.
        </p>
        <p style="font-size: large">
        Para gerar o gráfico inicial, utilize o botão abaixo para enviar o arquivo de dados do teste.
        </p>
        
        <h2 style="font-size: 25px">Fluxo de análise</h2>
        <ul>
            <li>Faça upload do arquivo CSV.</li>
            <li>Visualize o sinal completo.</li>
            <li>Analise os resultados estatísticos.</li>
        </ul>
    </div>
    """
)

st.divider()


# ===============================
# Sidebar
# ===============================


with st.sidebar:
    # TODO: Obter Logo Atualizada
    st.image("assets/logo.png")
    
    st.html(
        """
        <p style="text-align: center; color: lightgray; font-size: 13px">Potiguar Rocket Design</p>
        <hr style="color: gray">
        """
    )
    
    st.html(
        """
        <p style="text-align: center"> Upload do arquivo CSV </p>
        """
    )
    
    file = st.file_uploader(
        label="Upload do arquivo CSV",
        accept_multiple_files=False,
        type=["csv", "txt"],
        label_visibility="collapsed",
    )
    
    st.html(
        """
        <p style="text-align: center">Informe a tensão esperada do circuito.</p>
        """
    )
    
    tensao_esperada = st.number_input("Tensão", value=1.650)


# ===============================
# Upload de Dados
# ===============================


if file is None:
    st.info("Faça o upload de um arquivo na sidebar para iniciar a análise.")
    st.stop()

df_total, dados_por_canal = an.carregar_dados(file)


# ===============================
# Grafico
# ===============================


st.subheader("Gráfico dos Canais")

canais_disponiveis = sorted(df_total["ch"].unique())

canais_selecionados = st.multiselect(
    "Selecione os canais para visualizar:",
    options=canais_disponiveis,
    default=canais_disponiveis
)

df_plot = df_total[df_total["ch"].isin(canais_selecionados)].copy()
df_plot["ch"] = df_plot["ch"].astype(str)

fig = px.line(
    df_plot,
    x="amostra",
    y="tensao",
    color="ch",
    markers=False,
    title="Tensão medida por amostra",
    labels={
        "amostra": "Número da amostra",
        "tensao": "Tensão medida (V)",
        "ch": "Canal"
    }
)

fig.add_hline(
    y=tensao_esperada,
    line_dash="dash",
    annotation_text=f"Tensão esperada = {tensao_esperada:.3f} V",
    annotation_position="top left"
)

fig.update_layout(
    xaxis_title="Número da amostra",
    yaxis_title="Tensão medida (V)",
    legend_title="Canal",
    hovermode="x unified"
)

st.plotly_chart(fig, width="stretch")


# ===============================
# Estatísticas
# ===============================

st.divider()

st.subheader("Estatísticas dos Canais Selecionados")

estatisticas = an.obter_estatisticas_por_canal(
    dados_por_canal,
    tensao_esperada
)

if not canais_selecionados:
    st.warning("Selecione pelo menos um canal para visualizar as estatísticas.")
else:
    st.subheader("Tabela Resumo")

    linhas_resumo = []

    for canal in canais_selecionados:
        if canal not in estatisticas:
            continue

        stats = estatisticas[canal].copy()
        linhas_resumo.append(stats)

    if linhas_resumo:
        df_estatisticas = pd.DataFrame(linhas_resumo)

        df_estatisticas["media"] = df_estatisticas["media"].map(lambda x: f"{x:.4f} V")
        df_estatisticas["erro_absoluto"] = df_estatisticas["erro_absoluto"].map(lambda x: f"{x:.6f} V")
        df_estatisticas["erro_percentual"] = df_estatisticas["erro_percentual"].map(lambda x: f"{x:.4f} %")
        df_estatisticas["desvio_padrao"] = df_estatisticas["desvio_padrao"].map(lambda x: f"{x:.6f} V")
        df_estatisticas["minimo"] = df_estatisticas["minimo"].map(lambda x: f"{x:.4f} V")
        df_estatisticas["maximo"] = df_estatisticas["maximo"].map(lambda x: f"{x:.4f} V")
        df_estatisticas["ruido"] = df_estatisticas["ruido"].map(lambda x: f"{x:.6f} V")

        colunas_exibir = [
            "canal",
            "media",
            "erro_absoluto",
            "erro_percentual",
            "desvio_padrao",
            "minimo",
            "maximo",
            "ruido",
            "quantidade_amostras"
        ]

        st.dataframe(
            df_estatisticas[colunas_exibir],
            width="stretch"
        )
    else:
        st.info("Nenhuma estatística disponível para os canais selecionados.")