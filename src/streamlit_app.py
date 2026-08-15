import streamlit as st

pages = ["dashboard.py", "comparacao.py"]

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

pg = st.navigation(pages)

pg.run()