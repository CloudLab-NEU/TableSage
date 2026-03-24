import re
import collections
import string
import tiktoken
from openai import OpenAI
from typing import List, Dict, Any, Tuple, Union
import os
import jieba.posseg as pseg

PUNKS = set(string.punctuation) - {"_"}
STOPWORDS = {"i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"}

CELL_EXACT_MATCH_FLAG = "EXACTMATCH"
CELL_PARTIAL_MATCH_FLAG = "PARTIALMATCH"
COL_PARTIAL_MATCH_FLAG = "CPM"
COL_EXACT_MATCH_FLAG = "CEM"
TAB_PARTIAL_MATCH_FLAG = "TPM"
TAB_EXACT_MATCH_FLAG = "TEM"

def extract_question_skeleton(question: str) -> str:
    """
    Extract the structural skeleton of a question using POS tagging (jieba).
    Replaces LLM for speed and zero-shot entity removal.
    """
    words = pseg.cut(question)
    
    skeleton = []
    for word, flag in words:
        word = word.strip()
        if not word:
            continue
            
        # Keep existing underscores (from schema linking) paramount
        if word == '_':
            skeleton.append('_')
            continue
            
        if word in PUNKS or word.lower() in STOPWORDS:
            continue
            
        # Logical Decoupling: Mask Nouns (n), Numbers (m), Time (t)
        if flag.startswith('n') or flag.startswith('m') or flag == 't':
            skeleton.append('_')
        else:
            skeleton.append(word)
            
    # Clean up consecutive underscores
    result = " ".join(skeleton)
    result = re.sub(r'(_\s*)+', '_ ', result).strip()
    
    # Fallback if empty
    if not result:
        return "_"
        
    return result

def embedding_text(text, model=None, max_tokens=8096):
    if model is None:
        model = os.environ.get("EMBEDDING_MODEL", "text-embedding-ada-002")
    api_key = os.environ.get("EMBEDDING_API_KEY")
    api_base = os.environ.get("EMBEDDING_BASE_URL")
    
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE")

    client = OpenAI(
        api_key=api_key,
        base_url=api_base,
    )

    tokenizer = tiktoken.encoding_for_model(model)
    tokens = tokenizer.encode(text)

    if len(tokens) > max_tokens:
        text = tokenizer.decode(tokens[:max_tokens])

    res = client.embeddings.create(input=text, model=model)
    return res.data[0].embedding

def compute_schema_linking(question_tokens, header_tokens):
    def partial_match(x_list, y_list):
        x_str = " ".join(x_list).lower()
        y_str = " ".join(y_list).lower()
        if x_str in STOPWORDS or x_str in PUNKS:
            return False
        if re.search(rf"\b{re.escape(x_str)}\b", y_str):
            return True
        else:
            return False

    def exact_match(x_list, y_list):
        x_str = " ".join(x_list).lower()
        y_str = " ".join(y_list).lower()
        return x_str == y_str

    q_col_match = dict()
    n = min(5, len(question_tokens))
    while n > 0:
        for i in range(len(question_tokens) - n + 1):
            n_gram_list = [token.lower() for token in question_tokens[i:i + n]]
            n_gram = " ".join(n_gram_list)
            if len(n_gram.strip()) == 0:
                continue
            for col_id, col_tokens in enumerate(header_tokens):
                if exact_match(n_gram_list, col_tokens):
                    for q_id in range(i, i + n):
                        q_col_match[f"{q_id},{col_id}"] = COL_EXACT_MATCH_FLAG
            for col_id, col_tokens in enumerate(header_tokens):
                if partial_match(n_gram_list, col_tokens):
                    for q_id in range(i, i + n):
                        if f"{q_id},{col_id}" not in q_col_match:
                            q_col_match[f"{q_id},{col_id}"] = COL_PARTIAL_MATCH_FLAG
        n -= 1
    return {"q_col_match": q_col_match}

def compute_cell_value_linking(tokens, header_tokens, rows):
    headers = [" ".join(col_tokens) for col_tokens in header_tokens]

    def isnumber(word):
        try:
            float(word)
            return True
        except:
            return False

    def cell_value_partial_match(word, value):
        if not isinstance(value, str):
            value = str(value)
        word = str(word).lower()
        value = value.lower()
        return (f" {word} " in f" {value} " or 
                value.startswith(f"{word} ") or 
                value.endswith(f" {word}") or 
                value == word)

    def cell_value_exact_match(phrase, value):
        if not isinstance(value, str):
            value = str(value)
        phrase = str(phrase).lower()
        value = value.lower()
        return phrase == value

    num_date_match = {}
    cell_match = {}
    column_values = {}
    
    for col_id in range(len(headers)):
        column_values[col_id] = []
        for row in rows:
            if col_id < len(row):
                val = row[col_id]
                column_values[col_id].append(str(val).lower() if val is not None else "")

    column_types = {}
    for col_id in column_values:
        is_num = all(v == "" or isnumber(v) for v in column_values[col_id])
        column_types[col_id] = "number" if is_num else "text"

    for col_id in range(len(headers)):
        match_q_ids = []
        for q_id, word in enumerate(tokens):
            if not word.strip() or word.lower() in STOPWORDS or word in PUNKS:
                continue
            if isnumber(word) and column_types[col_id] == "number":
                num_date_match[f"{q_id},{col_id}"] = "NUMBER"
                continue
            for value in column_values[col_id]:
                if value and cell_value_partial_match(word, value):
                    match_q_ids.append(q_id)
                    break
        f = 0
        while f < len(match_q_ids):
            t = f + 1
            while t < len(match_q_ids) and match_q_ids[t] == match_q_ids[t-1] + 1:
                t += 1
            phrase = ' '.join(tokens[match_q_ids[f]:match_q_ids[t-1]+1])
            exact_match_found = any(v and cell_value_exact_match(phrase, v) for v in column_values[col_id])
            for q_id in range(match_q_ids[f], match_q_ids[t-1]+1):
                cell_match[f"{q_id},{col_id}"] = CELL_EXACT_MATCH_FLAG if exact_match_found else CELL_PARTIAL_MATCH_FLAG
            f = t
    return {"num_date_match": num_date_match, "cell_match": cell_match}

def match_shift(q_col_match, cell_match):
    q_id_to_match = collections.defaultdict(list)
    for k, v in q_col_match.items():
        q_id, c_id = map(int, k.split(','))
        q_id_to_match[q_id].append((v, c_id))
    
    priority = sorted([(len(v), k) for k, v in q_id_to_match.items()])
    matches = []
    new_q_col_match = {}
    
    for _, q_id in priority:
        potential = q_id_to_match[q_id]
        already_matched = [m for m in potential if m in matches]
        if not already_matched:
            exact = [m for m in potential if m[0] == COL_EXACT_MATCH_FLAG]
            res = exact if exact else potential
            matches.extend(res)
        else:
            res = already_matched
        for m in res:
            new_q_col_match[f"{q_id},{m[1]}"] = m[0]
            
    relevant_ids = set(q_id_to_match.keys())
    new_cell_match = {k: v for k, v in cell_match.items() if int(k.split(',')[0]) not in relevant_ids}
    return new_q_col_match, new_cell_match

def preprocess_header(header):
    if isinstance(header, (list, tuple)) and len(header) == 1 and isinstance(header[0], (list, tuple)):
        header = header[0]
    processed = []
    for col in header:
        processed.append(str(col).lower().split() if isinstance(col, str) else [str(col).lower()])
    return processed

def split_punctuation(tokens):
    """Separate punctuation from both sides of tokens (e.g., '(GDP)' -> '(', 'GDP', ')')"""
    result = []
    for token in tokens:
        if not token: continue
        
        # Leading punctuation
        l_punks = []
        while token and token[0] in PUNKS:
            l_punks.append(token[0])
            token = token[1:]
        result.extend(l_punks)
        
        if not token: continue
        
        # Trailing punctuation
        r_punks = []
        while token and token[-1] in PUNKS:
            r_punks.insert(0, token[-1])
            token = token[:-1]
            
        if token:
            if "-" in token and not (token.startswith("-") or token.endswith("-")):
                parts = token.split("-")
                for i, p in enumerate(parts):
                    if p: result.append(p)
                    if i < len(parts)-1: result.append("-")
            else:
                result.append(token)
        result.extend(r_punks)
    return result

def preprocess_question_tokens(question):
    if isinstance(question, list): return question
    if not isinstance(question, str): question = str(question)
    lines = [l for l in question.strip().split("\n") if l.strip() and not l.startswith(("Current ", "#"))]
    text = " ".join(lines) if lines else question
    return split_punctuation(text.split())

def mask_question_with_schema_linking(question, headers, rows, mask_tag="_", value_tag="_"):
    header_tokens = preprocess_header(headers)
    question_tokens = preprocess_question_tokens(question)
    sc_link = compute_schema_linking(question_tokens, header_tokens)
    cv_link = compute_cell_value_linking(question_tokens, header_tokens, rows)
    q_col_match, cell_match = match_shift(sc_link["q_col_match"], cv_link["cell_match"])

    def mask(toks, ids, tag):
        res = []
        for i, t in enumerate(toks):
            if i in ids:
                if not (res and res[-1] == tag): res.append(tag)
            else:
                res.append(t)
        return res

    val_ids = [int(k.split(',')[0]) for k in list(cv_link["num_date_match"].keys()) + list(cell_match.keys())]
    masked = mask(question_tokens, val_ids, value_tag)
    col_ids = [int(k.split(',')[0]) for k in q_col_match.keys()]
    masked = mask(masked, col_ids, mask_tag)
    return " ".join(masked)

def deal_question_skeleton(question: str, table: dict) -> Tuple[List[float], str]:
    header = table.get('header', [])
    rows = table.get('rows', [])
    masked_question = mask_question_with_schema_linking(question, header, rows)
    finally_skeleton = extract_question_skeleton(masked_question)
    print("finally_skeleton:", finally_skeleton)
    embedding = embedding_text(finally_skeleton)
    return embedding, finally_skeleton