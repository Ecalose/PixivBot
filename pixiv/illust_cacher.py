import os
import shutil
import typing as T
from functools import partial
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFile

from utils import settings, launch, CacheManager
from .pixiv_api import papi

domain: T.Optional[str] = settings["illust"]["domain"]
download_dir: str = settings["illust"]["download_dir"]
download_quantity: str = settings["illust"]["download_quantity"]
download_outdated_time: int = settings["illust"]["download_outdated_time"]
download_timeout: int = settings["illust"]["download_timeout"]
compress: bool = settings["illust"]["compress"]
compress_size: int = settings["illust"]["compress_size"]
compress_quantity: int = settings["illust"]["compress_quantity"]

__img_cache_manager = CacheManager()


async def start_illust_cacher():
    await __img_cache_manager.start()


async def stop_illust_cacher():
    await __img_cache_manager.stop()


async def cache_illust(illust: dict) -> bytes:
    """
    缓存给定illust，或从缓存中读取
    :param illust: 给定illust
    :return: illust的bytes
    """

    dirpath = Path("./" + download_dir)
    dirpath.mkdir(parents=True, exist_ok=True)

    if download_quantity == "original":
        if len(illust["meta_pages"]) > 0:
            url = illust["meta_pages"][0]["image_urls"]["original"]
        else:
            url = illust["meta_single_page"]["original_image_url"]
    else:
        url = illust["image_urls"][download_quantity]
    if domain is not None:
        url = url.replace("i.pximg.net", domain)

    # 从url中截取的文件名
    filename = os.path.basename(url)
    filepath = dirpath.joinpath(filename)

    b = await __img_cache_manager.get(filepath, partial(__download_and_compress, url),
                                      cache_outdated_time=download_outdated_time,
                                      timeout=download_timeout)
    return b


async def __download_and_compress(url: str) -> bytes:
    data = await launch(__fetch_data, url=url)
    if compress:
        data = await launch(__compress_illust, data)
    return data


def __fetch_data(url: str, referer='https://app-api.pixiv.net/') -> bytes:
    with BytesIO() as bio:
        rsp = papi.requests_call('GET', url, headers={'Referer': referer}, stream=True)
        shutil.copyfileobj(rsp.raw, bio)
        del rsp
        return bio.getvalue()


def __compress_illust(data: bytes) -> bytes:
    """
    压缩图片（图片以bytes形式传递）
    :param data: 图片
    """
    p = ImageFile.Parser()
    p.feed(data)
    img = p.close()

    w, h = img.size
    if w > compress_size or h > compress_size:
        ratio = min(compress_size / w, compress_size / h)
        img_cp = img.resize((int(ratio * w), int(ratio * h)), Image.ANTIALIAS)
    else:
        img_cp = img.copy()
    img_cp = img_cp.convert("RGB")

    with BytesIO() as bio:
        img_cp.save(bio, format="JPEG", optimize=True, quantity=compress_quantity)
        return bio.getvalue()
