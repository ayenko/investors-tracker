mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"you@example.com\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
enableCORS=false\n\
enableXsrfProtection=false\n\
port = $PORT\n\

[theme]
base = \"light\"

[ui]
hideTopBar = true
" > ~/.streamlit/config.toml
