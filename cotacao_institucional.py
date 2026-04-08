import sys
import asyncio
import re
from playwright.async_api import async_playwright
from fpdf import FPDF
from datetime import datetime

class CotadorBot:
    def __init__(self, item, quantidade):
        self.item = item
        self.quantidade = int(quantidade)
        self.resultados = []

    async def buscar_br(self, context):
        page = await context.new_page()
        try:
            # Busca no Google Shopping com parâmetros de localização brasileiros
            url = f"https://www.google.com.br/search?tbm=shop&q={self.item.replace(' ', '+')}&hl=pt-BR&gl=br"
            print(f"Navegando para: {url}")
            
            await page.goto(url, timeout=60000, wait_until="networkidle")
            
            # Rola a página para carregar resultados preguiçosos (lazy load)
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(3)

            # Captura todos os blocos que pareçam um produto (seletores variados para redundância)
            cards = await page.query_selector_all('div[data-docid], .sh-dgr__content, .sh-prc__content')
            
            print(f"Cards encontrados: {len(cards)}")

            for card in cards:
                if len(self.resultados) >= 3: break
                
                texto_completo = await card.inner_text()
                # Procura o padrão de preço brasileiro: R$ 1.234,56
                match_preco = re.search(r'R\$\s?(\d+[\d\.,]*)', texto_completo)
                
                if match_preco:
                    preco_raw = match_preco.group(1)
                    preco_val = float(preco_raw.replace('.', '').replace(',', '.'))
                    
                    # Tenta pegar o nome no H3 ou no primeiro link
                    nome_el = await card.query_selector('h3')
                    nome = await nome_el.inner_text() if nome_el else "Produto"
                    
                    # Tenta pegar a loja (geralmente texto após o preço ou em spans específicos)
                    loja = "Loja não identificada"
                    vendedores = ["Amazon", "Magalu", "Magazine Luiza", "Mercado Livre", "Casas Bahia", "Shopee", "Kabum"]
                    for v in vendedores:
                        if v.lower() in texto_completo.lower():
                            loja = v
                            break
                    
                    link_el = await card.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    link = "https://www.google.com.br" + href if href.startswith('/') else href

                    # CNPJ Automático para os grandes
                    cnpjs = {"amazon": "15.436.940/0001-03", "magalu": "47.960.950/0001-21", "mercado": "03.007.331/0001-41"}
                    cnpj_final = "Consultar Link"
                    for k, v in cnpjs.items():
                        if k in loja.lower(): cnpj_final = v

                    self.resultados.append({
                        "site": loja,
                        "cnpj": cnpj_final,
                        "preco_un": preco_val,
                        "link": link,
                        "vendedor": "Venda Direta" if cnpj_final != "Consultar Link" else "Marketplace"
                    })
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            await page.close()

    async def executar(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
            await self.buscar_br(context)
            await browser.close()

    def gerar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(190, 10, "MAPA DE PRECOS - DICOM v1.7", ln=True, align='C')
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(190, 7, f"ITEM: {self.item.upper()} | QTD: {self.quantidade}", ln=True)
        pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(5)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(45, 10, "Fornecedor", 1, 0, 'C', True)
        pdf.cell(30, 10, "CNPJ", 1, 0, 'C', True)
        pdf.cell(30, 10, "Unitario", 1, 0, 'C', True)
        pdf.cell(30, 10, "Total", 1, 0, 'C', True)
        pdf.cell(55, 10, "Status / Link", 1, 1, 'C', True)

        pdf.set_font("Helvetica", "", 7)
        soma = 0
        for res in self.resultados:
            total = res['preco_un'] * self.quantidade
            soma += res['preco_un']
            pdf.cell(45, 10, res['site'], 1)
            pdf.cell(30, 10, res['cnpj'], 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {res['preco_un']:,.2f}", 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {total:,.2f}", 1, 0, 'C')
            pdf.cell(55, 10, res['vendedor'], 1, 1, 'C', link=res['link'])

        if not self.resultados:
            pdf.set_text_color(255, 0, 0)
            pdf.multi_cell(190, 10, "ALERTA: O sistema de busca automatica nao retornou dados. Tente pesquisar por um termo mais genérico.")
        
        pdf.output("cotacao.pdf")

if __name__ == "__main__":
    bot = CotadorBot(sys.argv[1] if len(sys.argv) > 1 else "Item", int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    asyncio.run(bot.executar())
    bot.gerar_pdf()
