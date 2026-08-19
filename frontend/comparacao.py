import streamlit as st
import analise as an

# ===============================
# Configuração Geral
# ===============================


st.set_page_config(
    page_title="Comparação entre SPS",
    layout="wide"
)


# ===============================
# Comparação entre Amostragens
# ===============================

st.header("Comparação entre Taxas de Amostragem")

st.write(
    "Faça upload de vários arquivos de coleta (ex.: 500SPS, 1000SPS, 2000SPS...) "
    "para comparar os sinais no mesmo gráfico."
)

st.html(
    """
    <p style="text-align: center">Informe a tensão esperada do circuito.</p>
    """
)

tensao_esperada = st.number_input("Tensão", value=1.650)

arquivos_comparacao = st.file_uploader(
    label="Upload dos arquivos para comparação",
    accept_multiple_files=True,
    type=["csv", "txt"],
    key="upload_comparacao",
)

if arquivos_comparacao:
    # Permite renomear cada arquivo para um rótulo mais legível (ex.: "500 SPS")
    st.caption("Defina um rótulo para cada arquivo (usado como legenda no gráfico):")

    rotulos = {}
    colunas_rotulo = st.columns(len(arquivos_comparacao))

    for col, arquivo in zip(colunas_rotulo, arquivos_comparacao):
        with col:
            rotulo = st.text_input(
                f"Rótulo — {arquivo.name}",
                value=arquivo.name,
                key=f"rotulo_{arquivo.name}",
            )
            rotulos[rotulo] = arquivo

    try:
        df_comparacao = an.carregar_multiplos_arquivos(rotulos)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    canais_comparacao = sorted(df_comparacao["canal"].unique())

    canal_comparacao = st.selectbox(
        "Selecione o canal para comparar entre as coletas:",
        options=canais_comparacao,
    )

    fig_comparacao = an.plotar_comparacao_amostragem(
        df_comparacao,
        canal=canal_comparacao,
        tensao_esperada=tensao_esperada,
    )

    st.plotly_chart(
        fig_comparacao, 
        width="stretch",
        config={
            "toImageButtonOptions": {
                "filename": f"comparacao_canal{canal_comparacao}",
                "format": "png",
            }
        })
else:
    st.info("Faça o upload de dois ou mais arquivos acima para habilitar a comparação.")