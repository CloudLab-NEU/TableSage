from openai_api.openai_client import OpenAIClient

def build_sql_skeleton_prompt(question):
    prompt = (f"""You are an assistant for SQL structure extraction. Your task is to convert natural language questions into **SQL keyword structure templates**.

    ### Instructions:

    1. MUST only include the following SQL keywords:  
    SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT,  
    JOIN, LEFT JOIN, RIGHT JOIN, INNER JOIN, OUTER JOIN, ON,  
    IN, NOT IN, EXISTS, NOT EXISTS, BETWEEN, LIKE, IS NULL, IS NOT NULL,  
    AND, OR, NOT, CASE, WHEN, THEN, ELSE, END,  
    DISTINCT, UNION, UNION ALL,  
    COUNT, SUM, AVG, MIN, MAX

    2. Use double underscores `__` to replace **all** table names, column names, literal values, or expressions.

    3. Use only uppercase for SQL keywords.

    4. DO NOT include table names, column names, or any actual values. DO NOT explain your reasoning. DO NOT return anything except SQL keywords with placeholders.



    ### Example 1:
    - **Question:** Show the total number of orders for each customer
    - **Question Skeleton:** SELECT __, COUNT(__) FROM __ GROUP BY __

    ### Example 2:
    - **Question:** List each department and the average salary of its employees, ordered by average salary descending
    - **Question Skeleton:** SELECT __, AVG(__) FROM __ GROUP BY __ ORDER BY __ DESC

    ### Example 3:
    - **Question:** Show each employee's name and categorize them as 'Senior' or 'Junior' based on years of service
    - **Question Skeleton:** SELECT __, CASE WHEN __ > __ THEN __ ELSE __ END FROM __

    ### Example 4:
    - **Question:** Find customers who have not placed any orders
    - **Question Skeleton:** SELECT __ FROM __ WHERE NOT EXISTS (SELECT __ FROM __ WHERE __ = __)


    **Question:** {question}

    **SQL Skeleton:**""")
    return prompt

def generate_sql_skeleton(question):
    """
    根据原始问题生成 sql skeleton

    Args:
        question (str): 用户的问题
        model (str): 使用的模型名称，默认为 gpt-4
        
    Returns:
        dict: 包含生成的 sql skeleton
    """
    try:
        client = OpenAIClient()

        prompt_text = build_sql_skeleton_prompt(question)

        messages = [
            {"role": "system", "content": "You're an assistant that specializes in parsing the intent of table queries, and you're good at translating natural language questions into structured query representations."},
            {"role": "user", "content": prompt_text}
        ]

        response = client.get_llm_response(messages)

        return response
            
    except Exception as e:
        print(f"生成 question skeleton 时发生错误: {e}")
        return {"error": str(e)}