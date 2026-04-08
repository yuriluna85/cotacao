import sys
import asyncio
import re
from playwright.async_api import async_playwright
from fpdf import FPDF
from datetime import datetime

# Configurações Fixas
CEP_DESTINO = "41720-052"

class CotadorBot:
    def __init__(self, item, quantidade):
        self.item = item
        self.quantidade = int(quantidade)
        self.resultados = []

    async def buscar_loja(self, context, url_base, site_nome, seletores):
        page = await context.new_page()
        try:
            # Acessa a busca do site
            await page.goto(url_base + self.item.replace(" ", "+"), timeout=60000)
            
            # Localiza e clica no primeiro produto
            await page.wait_for_selector(seletores['item'], timeout=15000)
            await page.click(seletores['item'])
            
            # Aguarda o carregamento da página do produto
            await page.wait_for_load_state("networkidle")

            # Identifica o vendedor
            vendedor_txt = "Não identificado"
            try:
                vendedor_txt = await page.inner_text(seletores['vendedor'])
            except:
                pass

            # Extrai o preço
            preco_texto = await page.inner_text(seletores['preco'])
            preco_val = float(re.sub(r'[^\d,]', '', preco_texto).replace(',', '.'))
            
            # Verifica se é venda direta
            is_proprio = site_nome.lower() in vendedor_txt.lower()
            
            cnpjs = {
                "Amazon": "15.436.940/0001-03",
                "Magalu": "47.960.950/0001-21",
                "Mercado Livre": "03.007.331/0001-41"
            }

            self.resultados.append({
                "site": site_nome,
                "vendedor": vendedor_txt.strip(),
                "cnpj": cnpjs.get(site_nome) if is_proprio else "Consulte o Link",
                "preco_un": preco_val,
                "link": page.url,
                "proprio": is_proprio,
                "sucesso": True
            })

        except Exception as e:
            print(f"Erro ao buscar na {site_nome}: {e}")
        finally:
            await page.close()

    async def executar(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )

            tarefas = [
                self.buscar_loja(context, "https://www.amazon.com.br/s?k=", "Amazon", {
                    'item': "h2 a", 
                    'preco': ".a-price-whole", 
                    'vendedor': "#tabular-buybox-container"
                }),
                self.buscar_loja(context, "https://www.magazineluiza.com.br/busca/", "Magalu", {
                    'item': "h3[data-testid='product-title']", 
                    'preco': "p[data-testid='price-value']", 
                    'vendedor': "[data-testid='seller-info-container']"
                })
            ]
            
            await asyncio.gather(*tarefas)
            await browser.close()

    def gerar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        
        pdf.cell(190, 10, "MAPA COMPARATIVO DE PREÇOS", ln=True, align='C')
        pdf.set_font("Arial", "", 10)
        pdf.cell(190, 7, f"Item: {self.item.upper()}", ln=True)
        pdf.cell(190, 7, f"Quantidade: {self.quantidade} | Destino: CEP {CEP_DESTINO}", ln=True)
        pdf.cell(190, 7, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(5)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(35, 10, "Loja", 1, 0, 'C', True)
        pdf.cell(30, 10, "CNPJ", 1, 0, 'C', True)
        pdf.cell(30, 10, "Unitário", 1, 0, 'C', True)
        pdf.cell(30, 10, "Subtotal", 1, 0, 'C', True)
        pdf.cell(65, 10, "Vendedor", 1, 1, 'C', True)

        pdf.set_font("Arial", "", 7)
        soma_precos = 0
        for res in self.resultados:
            total = res['preco_un'] * self.quantidade
            soma_precos += res['preco_un']
            pdf.cell(35, 10, res['site'], 1)
            pdf.cell(30, 10, res['cnpj'], 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {res['preco_un']:,.2f}", 1, 0, 'C')
            pdf.cell(30, 10, f"R$ {total:,.2f}", 1, 0, 'C')
            pdf.cell(65, 10, res['vendedor'][:40], 1, 1)

        if len(self.resultados) < 3:
            media = soma_precos / len(self.resultados) if self.resultados else 0
            pdf.ln(5)
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(200, 0, 0)
            pdf.multi_cell(190, 6, f"OBSERVAÇÃO: Apenas {len(self.resultados)} cotações válidas encontradas. Média: R$ {media:,.2f}.")

        pdf.output("cotacao.pdf")

if __name__ == "__main__":
    bot = CotadorBot(sys.argv[1], sys.argv[2])
    asyncio.run(bot.executar())
    bot.gerar_pdf()
