import sys
import asyncio
import re
from playwright.async_api import async_playwright
from fpdf import FPDF
from datetime import datetime

CEP_DESTINO = "41720-052"

class CotadorBot:
    def __init__(self, item, quantidade):
        self.item = item
        self.quantidade = int(quantidade)
        self.resultados = []

    async def buscar_google_br(self, context):
        page = await context.new_page()
        try:
            # Força a busca no Google Shopping Brasil (.com.br)
            url = f"https://www.google.com.br/search?tbm=shop&q={self.item.replace(' ', '+')}&hl=pt-BR&gl=br"
            print(f"Buscando em domínios brasileiros: {url}")
            
            await page.goto(url, timeout=60000, wait_until="networkidle")
            
            # Espera pelos cards de produto brasileiros
            await page.wait_for_selector('div.sh-dgr__content', timeout=20000)
            items = await page.query_selector_all('div.sh-dgr__content')

            count = 0
            for item in items:
                if count >= 3: break
                
                try:
                    # Extração de Nome
                    nome_el = await item.query_selector('h3')
                    nome = await nome_el.inner_text() if nome_el else "Item"
                    
                    # Extração de Preço (Busca o padrão R$)
                    preco_txt = await item.inner_text()
                    match = re.search(r'R\$\s?(\d+[\d\.,]*)', preco_txt)
                    if not match: continue
                    
                    preco_val = float(match.group(1).replace('.', '').replace(',', '.'))
                    
                    # Identificação da Loja
                    loja_el = await item.query_selector('div.a33Sj, .I9Cve')
                    loja = await loja_el.inner_text() if loja_el else "Loja Brasileira"
                    
                    link_el = await item.query_selector('a')
                    link = "https://www.google.com.br" + await link_el.get_attribute('href')

                    # Lógica de CNPJ Institucional
                    cnpjs = {"amazon": "15.436.940/0001-03", "magalu": "47.960.950/0001-21", "mercado": "03.007.331/0001-41"}
                    cnpj_final = "Consulte o Link"
                    venda_direta = False
                    
                    for k, v in cnpjs.items():
                        if k in loja.lower():
                            cnpj_final = v
                            venda_direta = True

                    self.resultados.append({
                        "site": loja,
                        "vendedor": "Venda Direta" if venda_direta else "Marketplace",
                        "cnpj": cnpj_final,
                        "preco_un": preco_val,
                        "link": link,
                        "proprio": venda_direta
                    })
                    count += 1
                except:
                    continue
        except Exception as e:
            print(f"Erro na busca BR: {e}")
        finally:
            await page.close()

    async def executar(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Configuração de Localização (Salvador, Bahia)
            context = await browser.new_context(
                locale="pt-BR",
                timezone_id="America/Bahia",
                geolocation={"longitude": -38.5016, "latitude": -12.9714},
                permissions=["geolocation"],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            await self.buscar_google_br(context)
            await browser.close()

    def gerar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(190, 10, "MAPA DE PRECOS - DICOM BRASIL (v1.6)", ln=True, align='C')
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(190, 7, f"ITEM: {self.item.upper()} | QTD: {self.quantidade}", ln=True)
        pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(5)

        # Cabeçalho
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(45, 10, "Fornecedor", 1, 0, 'C', True)
        pdf.cell(30, 10, "CNPJ", 1, 0, 'C', True)
        pdf.cell(30, 10, "Unitario", 1, 0, 'C', True)
        pdf.cell(30, 10, "Total", 1, 0, 'C', True)
        pdf.cell(55, 10, "Status", 1, 1, 'C', True)

        pdf.set_font("Helvetica", "", 7)
        soma = 0
        for res in self.resultados:
            v_total = res['preco_un'] * self.quantidade
            soma += res['preco_un']
            pdf.cell(45, 10, res['site'][:30], 1)
            pdf.cell(30, 10, res['cnpj'], 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {res['preco_un']:,.2f}", 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {v_total:,.2f}", 1, 0, 'C')
            pdf.cell(55, 10, res['vendedor'], 1, 1, 'C')

        if not self.resultados:
            pdf.set_text_color(255, 0, 0)
            pdf.multi_cell(190, 10, "FALHA: O robô não encontrou resultados nos domínios .com.br. Tente um termo mais específico.")
        elif len(self.resultados) < 3:
            media = soma / len(self.resultados)
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(190, 6, f"OBSERVAÇÃO: Apenas {len(self.resultados)} orçamentos brasileiros obtidos. Média: R$ {media:,.2f}.")

        pdf.output("cotacao.pdf")

if __name__ == "__main__":
    item_p = sys.argv[1] if len(sys.argv) > 1 else "Papel A4"
    qtd_p = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    bot = CotadorBot(item_p, qtd_p)
    asyncio.run(bot.executar())
    bot.gerar_pdf()
