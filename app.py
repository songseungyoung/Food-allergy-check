
import os
import json

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List


# -----------------------------
# 1. 웹사이트 기본 설정
# -----------------------------
st.set_page_config(
    page_title="내 식품 성분 체크",
    page_icon="🥗",
    layout="centered"
)

st.title("🥗 내 식품 성분 체크")
st.write(
    "식품 성분표 사진을 올리고, "
    "내가 피해야 하는 성분이 있는지 확인해 봐."
)

st.info(
    "이 서비스는 AI 보조 도구야. "
    "특히 실제 식품 알레르기가 있다면 분석 결과만으로 "
    "식품의 안전성을 판단하면 안 돼."
)


# -----------------------------
# 2. API 키 및 클라이언트
# -----------------------------
def get_api_key():
    key = os.getenv("GOOGLE_API_KEY")

    if not key:
        try:
            key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            key = None

    return key


# -----------------------------
# 3. 분석 결과 데이터 구조
# -----------------------------
class IngredientAnalysisResult(BaseModel):
    detected_allergens: List[str] = Field(
        description="사용자가 피하는 성분과 일치하거나 관련된 원재료"
    )
    all_detected_ingredients: List[str] = Field(
        description="이미지에서 읽은 전체 원재료 목록"
    )
    warning_message: str = Field(
        description="분석 결과와 안전상 주의사항"
    )
    reason: str = Field(
        description="어떤 성분이 왜 매칭되었는지 설명"
    )
    uncertain_items: List[str] = Field(
        description="글자가 흐리거나 판독이 불확실한 부분. 없으면 빈 목록"
    )


# -----------------------------
# 4. AI 분석 함수
# -----------------------------
def analyze_food_label(image, avoid_list):
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "API 키가 설정되지 않았어. "
            "배포 설정의 GOOGLE_API_KEY를 확인해 줘."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
    식품 포장지의 원재료명 및 알레르기 유발 성분 표시를 분석해 줘.

    사용자가 피해야 하는 성분:
    {avoid_list}

    지침:
    1. 이미지에서 실제로 읽을 수 있는 원재료만 기록해.
    2. 사용자가 피하는 성분과 일치하는 항목을 찾아.
    3. 원재료명과 알레르기 표시를 근거로 매칭 이유를 설명해.
    4. 이미지에서 확인할 수 없는 정보를 추측하지 마.
    5. 글자가 흐리거나 잘렸거나 판독할 수 없는 부분은
       uncertain_items에 구체적으로 기록해.
    6. 검출 결과가 비어 있어도 안전하다고 단정하지 마.
    7. 교차오염 가능성이나 표시되지 않은 성분은 이미지 하나로
       확인할 수 없다는 점을 고려해.
    8. 실제 알레르기가 있는 사용자에게 안전을 보장하지 마.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IngredientAnalysisResult,
            temperature=0.1,
        ),
    )

    if not response.text:
        raise RuntimeError("AI가 분석 결과를 반환하지 않았어.")

    return json.loads(response.text)


# -----------------------------
# 5. 사용자 프로필 설정
# -----------------------------
default_ingredients = [
    "대두",
    "밀",
    "땅콩",
    "우유",
    "달걀",
    "메밀",
    "고등어",
    "게",
    "새우",
    "돼지고기",
    "복숭아",
    "토마토",
    "호두",
    "잣",
    "아황산류",
]

st.subheader("1. 피해야 하는 성분")

avoid_list = st.multiselect(
    "확인하고 싶은 성분을 선택해 줘",
    options=default_ingredients,
    default=["대두", "밀", "땅콩", "우유"],
)

custom_ingredients = st.text_input(
    "목록에 없는 성분 추가 (쉼표로 구분)",
    placeholder="예: 참깨, 특정 첨가물"
)

if custom_ingredients.strip():
    avoid_list += [
        item.strip()
        for item in custom_ingredients.split(",")
        if item.strip()
    ]

# 중복 제거
avoid_list = list(dict.fromkeys(avoid_list))


# -----------------------------
# 6. 이미지 업로드
# -----------------------------
st.subheader("2. 식품 성분표 사진")

uploaded_file = st.file_uploader(
    "식품 포장지의 원재료명 또는 알레르기 표시를 올려 줘",
    type=["jpg", "jpeg", "png", "webp"],
)

if uploaded_file:
    try:
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="업로드한 성분표", use_container_width=True)

        if st.button("🔎 성분 분석하기", type="primary"):
            if not avoid_list:
                st.warning("먼저 피해야 하는 성분을 선택해 줘.")
            else:
                with st.spinner("성분표를 분석하고 있어..."):
                    try:
                        result = analyze_food_label(image, avoid_list)

                        st.subheader("3. 분석 결과")

                        matched = result.get("detected_allergens", [])
                        uncertain = result.get("uncertain_items", [])

                        if matched:
                            st.error("⚠️ 확인이 필요한 성분이 발견됐어")
                            for item in matched:
                                st.write(f"- {item}")
                        else:
                            st.warning(
                                "선택한 성분과 일치하는 항목이 "
                                "검출되지 않았어. 안전하다는 뜻은 아니야."
                            )

                        st.write("**매칭 이유**")
                        st.write(result.get("reason", "설명 없음"))

                        st.write("**인식한 전체 원재료**")
                        ingredients = result.get(
                            "all_detected_ingredients", []
                        )

                        if ingredients:
                            for item in ingredients:
                                st.write(f"- {item}")
                        else:
                            st.write("원재료를 확인하지 못했어.")

                        st.write("**판독 불확실 항목**")
                        if uncertain:
                            for item in uncertain:
                                st.warning(item)
                        else:
                            st.write(
                                "AI가 별도로 불확실하다고 표시한 "
                                "항목은 없어. 다만 오인식이 없다는 "
                                "보장은 아니야."
                            )

                        st.info(
                            result.get("warning_message", "")
                        )

                        st.caption(
                            "AI 결과는 참고용이야. 실제 알레르기가 "
                            "있다면 제품의 공식 표시를 직접 확인하고, "
                            "불확실하면 제조사에 문의해 줘. "
                            "교차오염 여부도 별도로 확인해야 해."
                        )

                    except Exception as e:
                        st.error(
                            "분석에 실패했어. API 키, 인터넷 연결, "
                            "API 사용량 및 오류 내용을 확인해 줘."
                        )
                        st.caption(str(e))

    except Exception:
        st.error("이미지를 읽을 수 없어. 다른 이미지로 시도해 줘.")
else:
    st.caption("선명하게 촬영한 성분표 사진을 올리면 돼.")
