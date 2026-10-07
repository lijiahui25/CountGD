import os
from transformers import AutoTokenizer, BertModel


def get_tokenlizer(text_encoder_type):
    if not isinstance(text_encoder_type, str):
        if hasattr(text_encoder_type, "text_encoder_type"):
            text_encoder_type = text_encoder_type.text_encoder_type
        elif text_encoder_type.get("text_encoder_type", False):
            text_encoder_type = text_encoder_type.get("text_encoder_type")
        elif os.path.isdir(text_encoder_type) and os.path.exists(text_encoder_type):
            pass
        else:
            raise ValueError(
                f"Unknown type of text_encoder_type: {type(text_encoder_type)}"
            )
    print(f"final text_encoder_type: {text_encoder_type}")
    tokenizer = AutoTokenizer.from_pretrained(text_encoder_type)  # 核心
    print("load tokenizer done.")
    return tokenizer


def get_pretrained_language_model(text_encoder_type):
    if text_encoder_type == "bert-base-uncased" or (os.path.isdir(text_encoder_type) and os.path.exists(text_encoder_type)):
        return BertModel.from_pretrained(text_encoder_type)

    raise ValueError(f"Unknown text_encoder_type {text_encoder_type}")
