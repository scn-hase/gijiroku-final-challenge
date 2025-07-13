import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account

# --- アプリのUI部分 ---
st.title("Vertex AI 疎通確認テスト")
st.info("このアプリが正しく表示され、ボタンを押してAIから応答があれば、GCPとの接続は成功です。")

# --- 認証と初期化 ---
# この部分は実際の議事録アプリと全く同じ
try:
    # Streamlit CloudのSecretsから認証情報を読み込む
    creds_dict = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    project_id = creds_dict["project_id"]
    location = "asia-northeast1"  # 東京リージョン
    vertexai.init(project=project_id, location=location, credentials=creds)
except (FileNotFoundError, KeyError):
    # ローカル環境の場合
    st.error("Secretsが見つかりません。Streamlit Cloudで実行してください。")
    st.stop()

# --- テストボタン ---
if st.button("AIに質問する"):
    with st.spinner("AIからの応答を待っています..."):
        try:
            # --- API呼び出し ---
            model = GenerativeModel(model_name="gemini-1.5-flash-002")
            response = model.generate_content("日本の首都はどこですか？")
            
            st.subheader("AIからの応答:")
            st.success(response.text)

        except Exception as e:
            st.error("API呼び出し中にエラーが発生しました。")
            st.exception(e)