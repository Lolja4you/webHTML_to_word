import aiohttp
import asyncio
import re
import os
from tqdm import tqdm
import pypandoc
from bs4 import BeautifulSoup
import logging
import aiofiles
import colorlog

# Настройка логирования с colorlog
logger = colorlog.getLogger()
handler = colorlog.StreamHandler()
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Настройка кэша
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

async def fetch_html(url, semaphore):
    cache_path = os.path.join(CACHE_DIR, re.sub(r'[^a-zA-Z0-9]', '_', url) + ".html")

    if os.path.exists(cache_path):
        async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
            return await f.read()

    async with semaphore:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Ошибка при запросе {url}: {response.status}")

                    html_content = await response.text()

                    async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
                        await f.write(html_content)

                    return html_content
        except Exception as e:
            logger.error(f"Ошибка при загрузке {url}: {e}")
            return None

def sanitize_filename(title):
    """Очищает заголовок от недопустимых символов для имени файла."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '', title)
    return sanitized.strip()

async def download_and_process(url, semaphore):
    html_content = await fetch_html(url, semaphore)
    if html_content:
        await process_html(url, html_content)

async def process_html(url, html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.title.string if soup.title else 'document'
        sanitized_title = sanitize_filename(title)
        output_filename = f"{sanitized_title}.docx"

        logger.info(f"Обработка URL: {url}")

        # Удаляем изображения
        for img in soup.find_all('img'):
            img.decompose()

        # Преобразуем HTML в DOCX
        pypandoc.convert_text(str(soup), 'docx', format='html', outputfile=output_filename)
        logger.info(f"Файл сохранен как: {output_filename}")
    except Exception as e:
        logger.error(f"Ошибка при обработке URL {url}: {e}")

async def main():
    urls = '''
        https://ohrana-tryda.com/node/566
        https://ohrana-tryda.com/node/588
        https://ohrana-tryda.com/node/1040
        ....
    '''

    url_list = list(set(url.strip() for url in urls.split() if url.strip()))
    semaphore = asyncio.Semaphore(10)
    
    # Создаем прогресс-бар
    with tqdm(total=len(url_list), desc="Обработка файлов", unit="файл", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [time left: {remaining}]', dynamic_ncols=True) as pbar:
        tasks = []
        for url in url_list:
            task = asyncio.create_task(download_and_process(url, semaphore))
            task.add_done_callback(lambda _: pbar.update(1))  # Обновить прогресс бар по завершению задачи
            tasks.append(task)
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
