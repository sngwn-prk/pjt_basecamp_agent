from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser, OutputFixingParser
from langchain_core.messages import HumanMessage
from langchain_community.callbacks import get_openai_callback

# import os
# from dotenv import load_dotenv
# load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_API_KEY = st.secrets("OPENAI_API_KEY")

llm_4o_mini = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o-mini",
    max_tokens=4096,
    temperature=0,
    max_retries=2,
)

llm_o3 = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="o3",
    max_tokens=4096,
    timeout=None,
    max_retries=2,
)

def quiz_analyzer_science(img_input_base64):
    response_schemas = [
        ResponseSchema(
            name="answer", 
            description="The answer for the given problem"
        ),
        ResponseSchema(
            name="description", 
            description="The solution process for the given problem"),
        ResponseSchema(
            name="keywords", 
            description="The keywords of scientific concepts that you need to know to solve the given problem. If there are two or more keywords for the problem, separate them with commas (,) and output a maximum of three."
        )
    ]
    parser = StructuredOutputParser.from_response_schemas(response_schemas)
    output_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_4o_mini)
    format_instructions = output_parser.get_format_instructions()

    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"""
                # Role
                Your role is to output the answer(answer), the solution process (description), and the keywords needed to solve a given South Korean high school-level science problem (Image).
                - Answer: Provide the correct answer to the problem.
                - Description: Offer a detailed explanation of the solution process.
                - Keywords: List important terms or concepts necessary for solving the problem.

                # Instructions
                1. Answer according to the given output format (# OutputFormat). 
                If the problem cannot be solved, output 'None' for answer, description, and keywords.
                2. Only consider the environment defined within the problem itself.
                Do not assume facts or logic that go beyond what is provided.
                3. The solution process must be explained in detail at a level understandable to high school students.
                4. The answer must be given in Korean.
                5. For multiple-choice questions, do not alter the order or content of the answer choices; output the choice numbers and contents exactly as shown in the problem. 
                For short-answer questions, output the exact answer.
                
                # OutputFormat: {format_instructions}
                """
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_input_base64}"
                }
            }
        ]
    )
    chain = llm_o3 | output_parser

    try:
        with get_openai_callback() as cb:
            response = chain.invoke([message])
        usage_tokens = cb.total_tokens
        return usage_tokens, response
    except Exception as e:
        print(f"Error: {e}")
        return None, None
