"""
页面元素分析工具（Playwright 方案）

通过 Playwright 的页面 API 查找可交互元素。
"""
import json

from loguru import logger

from task_engine.executors.desktop_executor.tools.browser_session import get_page


async def page_analyze(element_type: str = "search") -> str:
    """
    通过 Playwright 分析页面可交互元素

    Args:
        element_type: 要查找的元素类型，支持 "search"、"input"、"button"

    Returns:
        str: JSON 格式的分析结果
    """
    valid_types = ("search", "input", "button")
    if element_type not in valid_types:
        element_type = "search"

    logger.info(f"🔍 [page_analyze] 通过 Playwright 查找 {element_type} 元素")

    try:
        page = await get_page()

        selectors = {
            "search": (
                'input[type="search"], input[type="text"][placeholder*="搜索"], '
                'input[type="text"][placeholder*="search" i], '
                'input[name*="search" i], input[name*="query" i], '
                'input[id*="search" i], input[class*="search" i], '
                'input[aria-label*="搜索"], input[aria-label*="search" i], '
                '[role="searchbox"], [role="search"] input'
            ),
            "input": 'input[type="text"], input:not([type]), textarea',
            "button": 'button, [role="button"], input[type="submit"], input[type="button"]',
        }

        selector = selectors.get(element_type, selectors["search"])
        elements = await page.query_selector_all(selector)

        result_elements = []
        for el in elements:
            box = await el.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                tag = await el.evaluate("e => e.tagName.toLowerCase()")
                placeholder = await el.get_attribute("placeholder") or ""
                aria_label = await el.get_attribute("aria-label") or ""
                el_id = await el.get_attribute("id") or ""

                desc_parts = []
                if placeholder:
                    desc_parts.append(f'placeholder="{placeholder}"')
                if aria_label:
                    desc_parts.append(f'aria-label="{aria_label}"')
                if el_id:
                    desc_parts.append(f'id="{el_id}"')
                desc = f"{tag}({', '.join(desc_parts)})" if desc_parts else tag

                # 构建可用于 click/type_text 的 CSS 选择器
                if el_id:
                    css_selector = f"#{el_id}"
                elif placeholder:
                    css_selector = f'{tag}[placeholder="{placeholder}"]'
                elif aria_label:
                    css_selector = f'{tag}[aria-label="{aria_label}"]'
                else:
                    css_selector = selector

                result_elements.append({
                    "description": desc,
                    "selector": css_selector,
                    "x": int(box["x"] + box["width"] / 2),
                    "y": int(box["y"] + box["height"] / 2),
                    "width": int(box["width"]),
                    "height": int(box["height"]),
                    "confidence": 0.95,
                })

        # search 未找到时回退到 input
        if not result_elements and element_type == "search":
            return await page_analyze("input")

        found = len(result_elements) > 0
        logger.info(f"🔍 [page_analyze] 完成: 找到 {len(result_elements)} 个 {element_type} 元素")

        return json.dumps(
            {"found": found, "query": element_type, "elements": result_elements},
            ensure_ascii=False,
        )

    except Exception as e:
        logger.warning(f"🔍 [page_analyze] 分析失败: {e}")
        return json.dumps(
            {"found": False, "query": element_type, "elements": [], "error": str(e)},
            ensure_ascii=False,
        )
