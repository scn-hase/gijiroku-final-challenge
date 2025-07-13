# app.py (完全版)

# === 必要なライブラリをまとめてインポート ===
import streamlit as st
import os
import datetime
import io

# Google Cloud & Vertex AI 関連
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account

# Wordファイル生成関連
from docx import Document

# === アプリのUI（ユーザーインターフェース）部分 ===

st.set_page_config(page_title="AI議事録作成アプリ", layout="wide")

st.title("AI議事録作成アプリ 📄✍️")
st.markdown("""
音声ファイル（MP3, WAV, M4A, MP4）をアップロードするだけで、AIが自動で文字起こしを行い、議事録の要約・決定事項・ToDoリストを作成します。
""")
st.info("※処理には数分かかることがあります。ファイルアップロード後、しばらくお待ちください。")


# ファイルアップロードのウィジェット
uploaded_file = st.file_uploader(
    "議事録を作成したい音声・動画ファイルを選択してください。",
    type=["mp3", "wav", "m4a", "mp4"]
)

# === メインの処理は、すべてこの if ブロックの中に入れる ===
# ファイルがアップロードされたら、以下の処理を順番に実行する
if uploaded_file is not None:
    
    st.success(f"ファイル「{uploaded_file.name}」がアップロードされました。処理を開始します。")

    # --- 1. 認証と初期化 ---
    # `with st.spinner` を使うと、処理中にローディング表示を出せる
    with st.spinner("ステップ1/5: クラウド環境に接続しています..."):
        try:
            # Streamlit CloudのSecretsから認証情報を読み込む
            creds_dict = st.secrets["gcp_service_account"]
            creds = service_account.Credentials.from_service_account_info(creds_dict)
            storage_client = storage.Client(credentials=creds)
            
            # あなたの新しいプロジェクトIDと、AIを動かすリージョンを指定
            project_id = "final-minutes-app" # 👈 【重要】あなたの新しいGCPプロジェクトIDに書き換えてください
            location = "asia-northeast1"           # 東京リージョン
            
            vertexai.init(project=project_id, location=location, credentials=creds)

        except (FileNotFoundError, KeyError):
            # ローカル環境で実行する場合のフォールバック
            st.info("ローカル環境として実行します。（Secretsが見つかりませんでした）")
            storage_client = storage.Client()
            
            project_id = "final-minutes-app" # 👈 【重要】あなたの新しいGCPプロジェクトIDに書き換えてください
            location = "asia-northeast1"           # 東京リージョン
            
            vertexai.init(project=project_id, location=location)

    # --- 2. Google Cloud Storageへのファイルアップロード ---
    gcs_uri = None
    with st.spinner("ステップ2/5: 音声ファイルを安全なクラウドにアップロードしています..."):
        # あなたの新しいGCSバケット名を指定
        bucket_name = "gijiroku-final-bucket" # 👈 【重要】あなたの新しいGCSバケット名に書き換えてください
        
        bucket = storage_client.bucket(bucket_name)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        blob_name = f"{timestamp}-{uploaded_file.name}"
        
        blob = bucket.blob(blob_name)
        blob.upload_from_file(uploaded_file, content_type=uploaded_file.type)
        
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        st.write(f"✅ ファイルのアップロードが完了しました: `{gcs_uri}`")


    # --- 3. AIによる文字起こし ---
    transcribed_text = None
    with st.spinner("ステップ3/5: AIが音声を文字に変換しています...（この処理は数分かかることがあります）"):
        # 使用するAIモデルを指定
        model = GenerativeModel(model_name="gemini-1.5-pro-preview-0514") # 動作が確認できた安定版Proモデル
        
        # GCS上の音声ファイルを指定
        audio_file = Part.from_uri(mime_type=uploaded_file.type, uri=gcs_uri)
        
        # AIへの指示（プロンプト）
        prompt = "この音声ファイルを日本語で、話者分離を意識しながら正確に文字起こししてください。"
        
        # AIにリクエストを送信
        response = model.generate_content([audio_file, prompt])
        
        transcribed_text = response.text
        st.subheader("文字起こし結果")
        with st.expander("全文を表示する"):
            st.write(transcribed_text)


    # --- 4. AIによる議事録生成 ---
    generated_minutes = None
    with st.spinner("ステップ4/5: AIが文字起こし内容を要約し、議事録を作成しています..."):
        # 議事録生成用の、より詳細なプロンプトを作成
        prompt_for_minutes = f"""
        あなたは非常に優秀なアシスタントです。
        以下の会議の文字起こしテキストを元に、要点を的確に捉えたプロフェッショナルな議事録を作成してください。

        以下のフォーマットを厳密に守って、日本語で出力してください。

        # 議事録

        ## 1. この会議の要約
        （会議全体の目的と結論を3〜5行で簡潔に記述してください）

        ## 2. 決定事項
        （会議で具体的に決定された事項を、箇条書きでリストアップしてください。決定事項がない場合は「特になし」と記載してください。）
        - 決定事項A
        - 決定事項B

        ## 3. ToDoリスト（担当者と期限）
        （会議で発生したタスクを、[ ]のチェックボックス形式でリストアップしてください。誰が(担当者)、いつまでに行うか(期限)を必ず明記してください。タスクがない場合は「特になし」と記載してください。）
        - [ ] 〇〇の調査（担当：佐藤さん、期限：YYYY-MM-DD）
        - [ ] △△の資料作成（担当：鈴木さん、期限：YYYY-MM-DD）
        
        ---
        
        # 元の文字起こしテキスト
        
        {transcribed_text}
        """
        
        # 再びAIにリクエストを送信
        response_minutes = model.generate_content(prompt_for_minutes)
        generated_minutes = response_minutes.text
        
        st.subheader("生成された議事録")
        st.markdown(generated_minutes)


    # --- 5. Wordファイル出力 ---
    with st.spinner("ステップ5/5: Wordファイルを生成しています..."):
        document = Document()
        document.add_heading('AI自動生成 議事録', 0)
        
        # 生成された議事録をドキュメントに追加
        # st.markdownと同じように表示するために、簡単なパーサーを実装
        for line in generated_minutes.split('\n'):
            line = line.strip()
            if line.startswith('### '):
                document.add_heading(line.replace('### ', ''), level=3)
            elif line.startswith('## '):
                document.add_heading(line.replace('## ', ''), level=2)
            elif line.startswith('# '):
                document.add_heading(line.replace('# ', ''), level=1)
            elif line.startswith('- '):
                # 箇条書きのインデントも考慮
                p = document.add_paragraph(style='List Bullet')
                p.add_run(line.replace('- ', ''))
            elif line: # 空行は無視
                document.add_paragraph(line)

        document.add_page_break()
        document.add_heading('文字起こし全文', level=1)
        document.add_paragraph(transcribed_text)
        
        # Wordファイルをメモリ上にバイナリデータとして保存
        file_stream = io.BytesIO()
        document.save(file_stream)
        file_stream.seek(0) # ストリームの先頭にポインタを戻す
    
    st.success("🎉 すべての処理が完了しました！以下から議事録をダウンロードできます。")

    # ダウンロードボタンを表示
    st.download_button(
        label="議事録をWordファイルでダウンロード",
        data=file_stream,
        file_name=f"議事録_{os.path.splitext(uploaded_file.name)[0]}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )