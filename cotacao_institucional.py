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

    async def buscar_ml(self, context):
        page = await context.new_page()
        try:
            # Mercado Livre é muito mais estável para automação sem bloqueio
            url = f"https://lista.mercadolivre.com.br/{self.item.replace(' ', '-')}"
            print(f"Buscando no Mercado Livre: {url}")
            
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Localiza os cards de produtos
            await page.wait_for_selector('.ui-search-result__wrapper', timeout=20000)
            items = await page.query_selector_all('.ui-search-result__wrapper')

            for item in items:
                if len(self.resultados) >= 3: break
                
                try:
                    nome_el = await item.query_selector('.ui-search-item__title')
                    nome = await nome_el.inner_text() if nome_el else "Produto"
                    
                    preco_el = await item.query_selector('.poly-price__current .and-fraction')
                    preco_txt = await preco_el.inner_text() if preco_el else "0"
                    preco_val = float(preco_txt.replace('.', '').replace(',', '.'))
                    
                    link_el = await item.query_selector('a.ui-search-link')
                    link = await link_el.get_attribute('href')

                    # Para o Mercado Livre, usamos o CNPJ da matriz para cotações oficiais
                    self.resultados.append({
                        "site": "Mercado Livre",
                        "cnpj": "03.007.331/0001-41",
                        "preco_un": preco_val,
                        "link": link,
                        "vendedor": "Venda Direta / Full"
                    })
                except:
                    continue
        except Exception as e:
            print(f"Erro na coleta: {e}")
        finally:
            await page.close()

    async def executar(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
            await self.buscar_ml(context)
            await browser.close()

    def gerar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(190, 10, "MAPA DE PRECOS - DICOM v1.8", ln=True, align='C')
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(190, 7, f"ITEM: {self.item.upper()} | QTD: {self.quantidade}", ln=True)
        pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(5)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(45, 10, "Fornecedor", 1, 0, 'C', True)
        pdf.cell(30, 10, "CNPJ", 1, 0, 'C', True)
        pdf.cell(30, 10, "Unitário", 1, 0, 'C', True)
        pdf.cell(30, 10, "Total", 1, 0, 'C', True)
        pdf.cell(55, 10, "Link", 1, 1, 'C', True)

        pdf.set_font("Helvetica", "", 7)
        soma = 0
        for res in self.resultados:
            total = res['preco_un'] * self.quantidade
            soma += res['preco_un']
            pdf.cell(45, 10, res['site'], 1)
            pdf.cell(30, 10, res['cnpj'], 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {res['preco_un']:,.2f}", 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {total:,.2f}", 1, 0, 'C')
            pdf.cell(55, 10, "Clique para Abrir", 1, 1, 'C', link=res['link'])

        if not self.resultados:
            pdf.set_text_color(255, 0, 0)
            pdf.multi_cell(190, 10, "ERRO: Os sites de busca bloquearam o acesso automatizado. Tente novamente em instantes.")
        
        pdf.output("cotacao.pdf")

if __name__ == "__main__":
    bot = CotadorBot(sys.argv[1], int(sys.argv[2]))
    asyncio.run(bot.executar())
    bot.gerar_pdf()
