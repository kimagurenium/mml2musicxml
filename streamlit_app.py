import itertools

import streamlit as st

import mml2musicxml


st.title("mml2musicxml")

if "init" not in st.session_state:
    st.session_state.init = True

    st.session_state.title = ""
    st.session_state.program = ""
    st.session_state.minified = False

    if "title" in st.query_params:
        st.session_state.title = st.query_params["title"]

    if "mml" in st.query_params:
        st.session_state.program = st.query_params["mml"]
    
    if "minified" in st.query_params:
        st.session_state.minified = True

"""
## MML
"""

st.text_input("Title", key="title")
st.text_area("MML", key="program")
st.toggle("Minify XML", key="minified")

scores: list[str | None] = []

try:
    scores = mml2musicxml.run(
        st.session_state.program,
        minified=st.session_state.minified,
    )

except mml2musicxml.ParsingError as e:
    st.error(f"MML parsing error at line {e.line}, column {e.column}.")
    st.text(str(e))

except mml2musicxml.CompilationError as e:
    st.error(f"MML compilation error.")
    st.text(str(e))

except mml2musicxml.Error:
    st.error(f"Internal error.")

"""
## MusicXML
"""

if scores:
    for channel, score in zip(itertools.count(), scores):
        if not score:
            continue
    
        f"""
        ### Channel {channel}
        """
    
        with st.expander("MusicXML"):
            st.code(score, language="xmlDoc")
    
        file_name = (st.session_state.title or "Untitled")
    
        if channel != 0:
            file_name += " " + str(channel)
    
        file_name += ".musicxml"
    
        st.download_button(
            label="Download",
            data=score,
            file_name=file_name,
            mime="application/vnd.recordare.musicxml+xml",
        )

else:
    "Not available"
