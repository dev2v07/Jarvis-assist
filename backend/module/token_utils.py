import tiktoken


# --------------------------------
# SUPPORTED ENCODINGS
# --------------------------------

ENCODINGS = {
    "gpt-4": "cl100k_base",
    "gpt-4o": "cl100k_base",
    "gpt-4o-mini": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "text-davinci-003": "p50k_base",
}


# --------------------------------
# CONTEXT LIMITS
# --------------------------------

MAX_CONTEXT = {
    "gpt-4": 8192,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 4096,
    "text-davinci-003": 4096,
}


# --------------------------------
# GET ENCODER
# --------------------------------

def get_encoder(model_name):

    encoding_name = ENCODINGS.get(model_name, "cl100k_base")

    return tiktoken.get_encoding(encoding_name)


# --------------------------------
# TOKEN COUNT
# --------------------------------

def count_tokens(model_name: str, text: str):

    try:

        enc = get_encoder(model_name)

        return len(enc.encode(text))

    except Exception:

        # fallback approximation

        return int(len(text) / 4)


# --------------------------------
# CONTEXT LIMIT
# --------------------------------

def get_max_context_length(model_name: str):

    return MAX_CONTEXT.get(model_name, 4096)


# --------------------------------
# TOKEN BIAS FOR TASK PARSER
# --------------------------------

def get_token_ids_for_task_parsing(model_name):

    enc = get_encoder(model_name)

    text = """
    {"task": "text-classification",
    "summarization",
    "translation",
    "question-answering",
    "conversational",
    "text-generation",
    "object-detection",
    "image-classification",
    "image-to-text",
    "text-to-image",
    "image-segmentation",
    "text-to-speech",
    "automatic-speech-recognition",
    "args",
    "text",
    "path",
    "dep",
    "id",
    "<GENERATED>-"}
    """

    tokens = enc.encode(text)

    return list(set(tokens))


# --------------------------------
# TOKEN BIAS FOR MODEL CHOICE
# --------------------------------

def get_token_ids_for_choose_model(model_name):

    enc = get_encoder(model_name)

    text = '{"id": "reason"}'

    tokens = enc.encode(text)

    return list(set(tokens))