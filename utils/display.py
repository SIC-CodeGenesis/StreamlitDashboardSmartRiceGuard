import streamlit as st
import pandas as pd

def display_dict_to_ui(data_dict, title="Dictionary Data", expandable=True):
    """
    Menampilkan dictionary sebagai UI Streamlit yang estetis
    
    Parameters:
    - data_dict: Dictionary yang akan ditampilkan
    - title: Judul untuk section UI
    - expandable: Jika True, tampilan dalam expander
    """
    
    # Styling untuk tampilan
    st.markdown("""
    <style>
    .dict-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .dict-key {
        font-weight: bold;
        color: #2c3e50;
    }
    .dict-value {
        color: #34495e;
    }
    </style>
    """, unsafe_allow_html=True)

    # Container utama
    if expandable:
        with st.expander(title, expanded=True):
            _render_dict(data_dict)
    else:
        st.subheader(title)
        _render_dict(data_dict)

def _render_dict(data_dict):
    """Helper function untuk render dictionary"""
    with st.container():
        # Konversi dict ke dataframe untuk tampilan tabel
        df = pd.DataFrame(list(data_dict.items()), columns=['Key', 'Value'])
        
        # Tampilkan dalam format card-like
        for idx, row in df.iterrows():
            st.markdown(
                f"""
                <div class='dict-container'>
                    <span class='dict-key'>{row['Key']}</span>: 
                    <span class='dict-value'>{row['Value']}</span>
                </div>
                """,
                unsafe_allow_html=True
            )