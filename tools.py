from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from dotenv import load_dotenv
import os
import requests
from langchain.agents import Tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from datetime import datetime
from markdown_pdf import MarkdownPdf, Section



load_dotenv(override=True)
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"
serper = GoogleSerperAPIWrapper()

async def playwright_tools():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


def push(text: str):
    """Send a push notification to the user"""
    requests.post(pushover_url, data = {"token": pushover_token, "user": pushover_user, "message": text})
    return "success"


def get_file_tools():
    toolkit = FileManagementToolkit(root_dir="sandbox")
    return toolkit.get_tools()


def generate_pdf_from_markdown(markdown_content: str, filename: str = None) -> str:
    """Generate a PDF file from markdown content and save it to the sandbox directory.
    
    Args:
        markdown_content: The markdown text to convert to PDF
        filename: Optional filename for the PDF. If not provided, generates a timestamped filename.
    
    Returns:
        The path to the generated PDF file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.pdf"
    
    # Ensure filename ends with .pdf
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    
    # Create full path in sandbox directory
    sandbox_dir = "sandbox"
    os.makedirs(sandbox_dir, exist_ok=True)
    pdf_path = os.path.join(sandbox_dir, filename)
    
    # Convert markdown to PDF using markdown-pdf library
    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(markdown_content))
    pdf.save(pdf_path)
    
    return f"PDF generated successfully at: {pdf_path}"


async def other_tools():
    push_tool = Tool(name="send_push_notification", func=push, description="Use this tool when you want to send a push notification")
    file_tools = get_file_tools()

    tool_search =Tool(
        name="search",
        func=serper.run,
        description="Use this tool when you want to get the results of an online web search"
    )

    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)
    
    pdf_tool = Tool(
        name="generate_pdf_from_markdown",
        func=generate_pdf_from_markdown,
        description="Use this tool when you need to convert markdown content to a PDF document. "
                   "Provide the markdown content as a string, and optionally a filename. "
                   "The PDF will be saved in the sandbox directory. "
                   "Example: generate_pdf_from_markdown('# Title\\n\\nContent here', 'document.pdf')"
    )
    
    return file_tools + [push_tool, tool_search, wiki_tool, pdf_tool]

