import re
import collections
import nltk.corpus
import string
import spacy
import tiktoken
from openai import OpenAI
from typing import List, Dict, Any, Tuple,Union
import os
# nltk.download('stopwords')
CELL_EXACT_MATCH_FLAG = "EXACTMATCH"
CELL_PARTIAL_MATCH_FLAG = "PARTIALMATCH"
COL_PARTIAL_MATCH_FLAG = "CPM"
COL_EXACT_MATCH_FLAG = "CEM"
TAB_PARTIAL_MATCH_FLAG = "TPM"
TAB_EXACT_MATCH_FLAG = "TEM"

from dotenv import load_dotenv
load_dotenv()

STOPWORDS = set(nltk.corpus.stopwords.words('english'))
PUNKS = set(a for a in string.punctuation)

def extract_question_skeleton(question):
    nlp = spacy.load("en_core_web_sm")

    QUESTION_WORDS = {"what", "which", "who", "whom", "whose", "where", "when", "why", "how"}
    question = re.sub(r'(["\'])(.*?)(\1)', lambda m: '_' * len(m.group(0)), question)

    doc = nlp(question)
    skeleton = []
    for token in doc:
        if token.text.lower() in QUESTION_WORDS:
            skeleton.append(token.text)
        elif token.pos_ in ['NOUN', 'PROPN', 'PRON']:
            skeleton.append('_')
        else:
            skeleton.append(token.text)

    final_skeleton = []
    previous_token = ""
    for token in skeleton:
        if token == "_" and previous_token == "_":
            continue
        final_skeleton.append(token)
        previous_token = token

    return ' '.join(final_skeleton)

def embedding_text(text, model="text-embedding-ada-002", max_tokens=8000):
    api_key = os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("OPENAI_API_BASE")
    client = OpenAI(
        api_key=api_key,
        base_url=api_base,
    )
    embedding_model = "text-embedding-ada-002"
    max_tokens = 8000
    """
    Call OpenAI Embedding API, truncate if text is too long.
    """
    tokenizer = tiktoken.encoding_for_model(embedding_model)
    
    tokens = tokenizer.encode(text)

    if len(tokens) > max_tokens:
        print(f"Text too long, truncated to {max_tokens} tokens (original length: {len(tokens)} tokens)")
        text = tokenizer.decode(tokens[:max_tokens])

    res = client.embeddings.create(input=text, model=model)
    return res.data[0].embedding

def compute_schema_linking(question_tokens, header_tokens):
    """
    Compute linking relationship between question and table headers (column names)
    Args:
        question_tokens: Question token list
        header_tokens: Preprocessed column name token list
    Returns:
        Dictionary containing matching relationships between question words and column names
    """
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

def compute_cell_value_linking(tokens: List[str], header_tokens: List[List[str]], rows: List[List[Any]]) -> Dict[str, Dict[str, str]]:
    """
    Compute linking relationship between question and table cell values
    Args:
        tokens: Tokenized question
        header_tokens: Preprocessed column name token list
        rows: Table row data
    Returns:
        Dictionary containing matching relationships between question words and cell values
    """
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
                value = row[col_id]
                if isinstance(value, str):
                    value = value.lower()
                column_values[col_id].append(value)

    column_types = {}
    for col_id in column_values:
        is_number = True
        for val in column_values[col_id]:
            if val and not isnumber(str(val)):
                is_number = False
                break
        column_types[col_id] = "number" if is_number else "text"

    for col_id in range(len(headers)):
        match_q_ids = []
        for q_id, word in enumerate(tokens):
            if len(word.strip()) == 0 or word.lower() in STOPWORDS or word in PUNKS:
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
            q_f, q_t = match_q_ids[f], match_q_ids[t-1] + 1
            phrase = ' '.join(tokens[q_f:q_t])
            exact_match_found = False
            for value in column_values[col_id]:
                if value and cell_value_exact_match(phrase, value):
                    exact_match_found = True
                    break
            for q_id in range(q_f, q_t):
                cell_match[f"{q_id},{col_id}"] = (CELL_EXACT_MATCH_FLAG if exact_match_found 
                                                 else CELL_PARTIAL_MATCH_FLAG)
            f = t
    return {"num_date_match": num_date_match, "cell_match": cell_match}

def match_shift(q_col_match: Dict[str, str], cell_match: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Resolve conflicts from multiple matches of question words, optimize matching results
    
    Args:
        q_col_match: Matching relationship between question words and column names
        cell_match: Matching relationship between question words and cell values
        
    Returns:
        Optimized column matching and cell matching dictionaries
    """
    q_id_to_match = collections.defaultdict(list)
    
    for match_key in q_col_match.keys():
        q_id = int(match_key.split(',')[0])
        c_id = int(match_key.split(',')[1])
        type = q_col_match[match_key]
        q_id_to_match[q_id].append((type, c_id))
    
    relevant_q_ids = list(q_id_to_match.keys())

    priority = []
    for q_id in q_id_to_match.keys():
        q_id_to_match[q_id] = list(set(q_id_to_match[q_id]))
        priority.append((len(q_id_to_match[q_id]), q_id))
    priority.sort()
    
    matches = []
    new_q_col_match = dict()
    
    for _, q_id in priority:
        if not list(set(matches) & set(q_id_to_match[q_id])):
            exact_matches = [match for match in q_id_to_match[q_id] 
                             if match[0] == COL_EXACT_MATCH_FLAG]
            
            if exact_matches:
                res = exact_matches
            else:
                res = q_id_to_match[q_id]
            matches.extend(res)
        else:
            res = list(set(matches) & set(q_id_to_match[q_id]))
        
        for match in res:
            type, c_id = match
            new_q_col_match[f'{q_id},{c_id}'] = type

    new_cell_match = {}
    for match_key in cell_match.keys():
        q_id = int(match_key.split(',')[0])
        if q_id in relevant_q_ids:
            continue
        new_cell_match[match_key] = cell_match[match_key]

    return new_q_col_match, new_cell_match

def preprocess_header(header):
    """
    Uniformly process header into a list of token lists
    """
    if isinstance(header, (list, tuple)) and len(header) == 1 and isinstance(header[0], (list, tuple)):
        header = header[0]
    processed = []
    for col in header:
        if isinstance(col, str):
            processed.append(col.lower().split())
        else:
            processed.append([str(col).lower()])
    return processed

def preprocess_question_tokens(question):
    """Preprocess various input formats and convert to token list"""
    if isinstance(question, list):
        return question
    
    if isinstance(question, str):
        lines = question.strip().split("\n")
        
        question_lines = []
        for line in lines:
            if not line.startswith("Current ") and not line.startswith("#") and line.strip():
                question_lines.append(line)
        
        if not question_lines:
            tokens = question.split()
            return split_punctuation(tokens)
        
        question_text = " ".join(question_lines)
        tokens = question_text.split()
        return split_punctuation(tokens)
    
    return preprocess_question_tokens(str(question))

def split_punctuation(tokens):
    """Separate punctuation marks"""
    result = []
    for token in tokens:
        if token and token[-1] in PUNKS:
            result.append(token[:-1])
            result.append(token[-1])
        elif "-" in token and not token.startswith("-") and not token.endswith("-"):
            parts = token.split("-")
            for i, part in enumerate(parts):
                if part:
                    result.append(part)
                if i < len(parts) - 1:
                    result.append("-")
        else:
            result.append(token)
    return result

def mask_question_with_schema_linking(question: Union[str, List[str], Tuple[str, ...]], 
                                     headers: List[str], 
                                     rows: List[List[Any]], 
                                     mask_tag: str = "_", 
                                     value_tag: str = "_") -> str:
    """
    Mark and process questions by replacing words related to column names and values with tags
    
    Args:
        question: Original question, can be string, list or tuple
        headers: Table column name list
        rows: Table row data
        mask_tag: Column name tag
        value_tag: Value tag
        
    Returns:
        Tagged and processed question
    """

    header_tokens = preprocess_header(headers)
    question_tokens = preprocess_question_tokens(question)

    sc_link = compute_schema_linking(question_tokens, header_tokens)
    
    cv_link = compute_cell_value_linking(question_tokens, header_tokens, rows)
    
    q_col_match = sc_link["q_col_match"]
    num_date_match = cv_link["num_date_match"]
    cell_match = cv_link["cell_match"]
    
    q_col_match, cell_match = match_shift(q_col_match, cell_match)

    def mask(question_toks: List[str], mask_ids: List[int], tag: str) -> List[str]:
        """Replace words at specified indices with tags"""
        new_question_toks = []
        for id, tok in enumerate(question_toks):
            if id in mask_ids:
                if id > 0 and new_question_toks and new_question_toks[-1] == tag:
                    continue
                new_question_toks.append(tag)
            else:
                new_question_toks.append(tok)
        return new_question_toks

    num_date_match_ids = [int(match.split(',')[0]) for match in num_date_match]
    cell_match_ids = [int(match.split(',')[0]) for match in cell_match]
    value_match_q_ids = num_date_match_ids + cell_match_ids
    masked_tokens = mask(question_tokens, value_match_q_ids, value_tag)

    q_col_match_ids = [int(match.split(',')[0]) for match in q_col_match]
    masked_tokens = mask(masked_tokens, q_col_match_ids, mask_tag)
    
    return " ".join(masked_tokens)

def deal_question_skeneton(question: str,table:dict) -> str:
    header = table.get('header', [])
    rows = table.get('rows', [])
    masked_question = mask_question_with_schema_linking(question, header, rows)
    finally_skeleton = extract_question_skeleton(masked_question)
    print("finally_skeleton:", finally_skeleton)
    embedding = embedding_text(finally_skeleton)

    return embedding,finally_skeleton