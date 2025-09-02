# app.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# Configuración de la página
st.set_page_config(
    page_title="Calculadora DCF - Valor Intrínseco",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("📈 Calculadora de Valor Intrínseco - Método DCF")
st.markdown("""
Esta aplicación calcula el *valor intrínseco* de una acción utilizando el método de *Flujo de Caja Descontado (DCF)*.
Los datos financieros se obtienen en tiempo real desde Yahoo Finance.

### ¿Cómo funciona?
1. Ingresa el ticker de la acción (ej: AAPL, MSFT, TSLA)
2. Ajusta los parámetros del modelo según tu análisis
3. Explora los resultados y gráficos
""")

# Sidebar para inputs
st.sidebar.header("Parámetros de Entrada")

# Input del ticker
ticker_symbol = st.sidebar.text_input("Símbolo del ticker", "AAPL").upper()

# Parámetros del modelo
st.sidebar.subheader("Parámetros del Modelo")
years_projection = st.sidebar.slider("Años de proyección", 5, 15, 10)
growth_rate = st.sidebar.slider("Tasa de crecimiento inicial (%)", 0.0, 20.0, 5.0) / 100
terminal_growth = st.sidebar.slider("Tasa de crecimiento terminal (%)", 0.0, 5.0, 2.5) / 100
discount_rate = st.sidebar.slider("Tasa de descuento (WACC %)", 5.0, 15.0, 10.0) / 100
debt_to_equity = st.sidebar.slider("Deuda/Patrimonio", 0.0, 2.0, 0.5)
cost_of_debt = st.sidebar.slider("Costo de la deuda (%)", 2.0, 10.0, 5.0) / 100

# Función para obtener datos financieros
@st.cache_data(ttl=3600, show_spinner="Obteniendo datos financieros...")  # Cache por 1 hora
def get_financial_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Obtener cash flow statements
        cash_flow = stock.cashflow
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        # Extraer Free Cash Flow
        fcf = None
        if not cash_flow.empty:
            if 'Free Cash Flow' in cash_flow.index:
                fcf = cash_flow.loc['Free Cash Flow']
            elif 'Operating Cash Flow' in cash_flow.index and 'Capital Expenditure' in cash_flow.index:
                fcf = cash_flow.loc['Operating Cash Flow'] - cash_flow.loc['Capital Expenditure']
            
        # Obtener datos relevantes
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        shares_outstanding = info.get('sharesOutstanding', 0)
        beta = info.get('beta', 1.0)
        debt = info.get('totalDebt', 0)
        cash = info.get('cash', 0)
        
        return {
            'fcf': fcf,
            'financials': financials,
            'balance_sheet': balance_sheet,
            'info': info,
            'current_price': current_price,
            'shares_outstanding': shares_outstanding,
            'beta': beta,
            'debt': debt,
            'cash': cash
        }
    except Exception as e:
        st.error(f"Error obteniendo datos para {ticker}: {str(e)}")
        return None

# Función para calcular WACC
def calculate_wacc(beta, risk_free_rate=0.042, market_return=0.09, 
                  debt_to_equity=0.5, cost_of_debt=0.05, tax_rate=0.25):
    # Costo de equity usando CAPM
    cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
    
    # Proporciones
    equity_weight = 1 / (1 + debt_to_equity)
    debt_weight = debt_to_equity / (1 + debt_to_equity)
    
    # WACC
    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    return wacc

# Función principal de valuación DCF
def dcf_valuation(fcf_data, growth_rate, terminal_growth, discount_rate, years_projection, shares_outstanding):
    if fcf_data is None or len(fcf_data) == 0:
        return None
        
    # Usar el FCF más reciente
    current_fcf = fcf_data.iloc[0] if hasattr(fcf_data, 'iloc') else fcf_data[0]
    
    # Proyectar flujos de caja futuros
    future_cash_flows = []
    for year in range(1, years_projection + 1):
        # Reducir gradualmente la tasa de crecimiento
        year_growth = growth_rate * np.exp(-0.1 * year)
        future_fcf = current_fcf * (1 + year_growth) ** year
        future_cash_flows.append(future_fcf)
    
    # Calcular valor terminal
    terminal_value = future_cash_flows[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    
    # Descontar flujos de caja a valor presente
    present_values = []
    for i, fcf in enumerate(future_cash_flows):
        pv = fcf / (1 + discount_rate) ** (i + 1)
        present_values.append(pv)
    
    # Descontar valor terminal
    terminal_pv = terminal_value / (1 + discount_rate) ** years_projection
    
    # Valor intrínseco total
    enterprise_value = sum(present_values) + terminal_pv
    
    # Valor intrínseco por acción
    intrinsic_value_per_share = enterprise_value / shares_outstanding
    
    return {
        'intrinsic_value': intrinsic_value_per_share,
        'enterprise_value': enterprise_value,
        'current_fcf': current_fcf,
        'present_values': present_values,
        'terminal_pv': terminal_pv,
        'future_cash_flows': future_cash_flows,
        'terminal_value': terminal_value
    }

# Obtener datos con manejo de errores
try:
    with st.spinner('Obteniendo datos financieros...'):
        financial_data = get_financial_data(ticker_symbol)
except Exception as e:
    st.error(f"Error al conectar con Yahoo Finance: {str(e)}")
    st.info("Esto puede deberse a limitaciones de la API o problemas de conexión. Intenta nuevamente en unos momentos.")
    financial_data = None

if financial_data and financial_data['fcf'] is not None:
    # Mostrar información de la empresa
    info = financial_data['info']
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Información de la Empresa")
        st.write(f"*Nombre:* {info.get('longName', 'N/A')}")
        st.write(f"*Sector:* {info.get('sector', 'N/A')}")
        st.write(f"*Industria:* {info.get('industry', 'N/A')}")
    
    with col2:
        st.subheader("Datos de Mercado")
        st.write(f"*Precio actual:* ${financial_data['current_price']:.2f}")
        st.write(f"*Beta:* {financial_data['beta']:.2f}")
        st.write(f"*Acciones en circulación:* {financial_data['shares_outstanding']:,.0f}")
    
    with col3:
        st.subheader("Estado Financiero")
        st.write(f"*Deuda total:* ${financial_data['debt']:,.0f}")
        st.write(f"*Efectivo:* ${financial_data['cash']:,.0f}")
        st.write(f"*Deuda Neta:* ${financial_data['debt'] - financial_data['cash']:,.0f}")
    
    # Calcular WACC
    wacc = calculate_wacc(
        beta=financial_data['beta'],
        debt_to_equity=debt_to_equity,
        cost_of_debt=cost_of_debt
    )
    
    # Mostrar parámetros utilizados
    st.subheader("Parámetros del Análisis DCF")
    param_col1, param_col2, param_col3, param_col4 = st.columns(4)
    
    with param_col1:
        st.metric("Tasa de crecimiento", f"{growth_rate*100:.2f}%")
        st.metric("Años de proyección", years_projection)
    
    with param_col2:
        st.metric("Crecimiento terminal", f"{terminal_growth*100:.2f}%")
        st.metric("WACC", f"{wacc*100:.2f}%")
    
    with param_col3:
        st.metric("Deuda/Patrimonio", f"{debt_to_equity:.2f}")
        st.metric("Costo de deuda", f"{cost_of_debt*100:.2f}%")
    
    with param_col4:
        st.metric("FCF actual", f"${financial_data['fcf'].iloc[0]/1e6:.2f}M")
        st.metric("Beta", f"{financial_data['beta']:.2f}")
    
    # Realizar valuación DCF
    with st.spinner('Calculando valor intrínseco...'):
        results = dcf_valuation(
            fcf_data=financial_data['fcf'],
            growth_rate=growth_rate,
            terminal_growth=terminal_growth,
            discount_rate=wacc,
            years_projection=years_projection,
            shares_outstanding=financial_data['shares_outstanding']
        )
    
    if results:
        # Mostrar resultados
        st.subheader("Resultados de la Valuación")
        
        res_col1, res_col2, res_col3 = st.columns(3)
        
        with res_col1:
            st.metric("Valor intrínseco por acción", f"${results['intrinsic_value']:.2f}")
            
        with res_col2:
            price_diff = results['intrinsic_value'] - financial_data['current_price']
            price_diff_pct = (price_diff / financial_data['current_price']) * 100
            st.metric("Diferencia con precio actual", f"${price_diff:.2f}", f"{price_diff_pct:.2f}%")
            
        with res_col3:
            if results['intrinsic_value'] > financial_data['current_price'] * 1.2:
                recommendation = "FUERTE COMPRA"
                color = "green"
            elif results['intrinsic_value'] > financial_data['current_price']:
                recommendation = "COMPRA"
                color = "lightgreen"
            elif results['intrinsic_value'] > financial_data['current_price'] * 0.8:
                recommendation = "MANTENER"
                color = "orange"
            else:
                recommendation = "VENDE"
                color = "red"
                
            st.markdown(f"### Recomendación: <span style='color:{color}'>{recommendation}</span>", 
                       unsafe_allow_html=True)
        
        # Gráfico de proyección de FCF
        st.subheader("Proyección de Flujo de Caja Libre")
        
        years = list(range(1, years_projection + 1))
        projected_fcf = results['future_cash_flows']
        
        fig = make_subplots(specs=[[{"secondary_y": False}]])
        fig.add_trace(
            go.Bar(x=years, y=projected_fcf, name="FCF Projected", marker_color='lightblue'),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=years, y=projected_fcf, name="Tendencia", line=dict(color='blue', width=2)),
            secondary_y=False,
        )
        
        fig.update_layout(
            title="Proyección de Flujo de Caja Libre",
            xaxis_title="Años",
            yaxis_title="FCF (Millones USD)",
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Desglose del valor
        st.subheader("Desglose del Valor")
        
        breakdown_data = {
            'Componente': ['Valor presente de FCF', 'Valor presente terminal'],
            'Valor (Millones USD)': [sum(results['present_values'])/1e6, results['terminal_pv']/1e6]
        }
        
        breakdown_df = pd.DataFrame(breakdown_data)
        breakdown_df['Porcentaje'] = (breakdown_df['Valor (Millones USD)'] / 
                                     breakdown_df['Valor (Millones USD)'].sum() * 100)
        
        st.dataframe(breakdown_df.style.format({
            'Valor (Millones USD)': '${:,.2f}',
            'Porcentaje': '{:.2f}%'
        }))
        
        # Análisis de sensibilidad
        st.subheader("Análisis de Sensibilidad")
        
        sens_growth = [growth_rate * 0.5, growth_rate, growth_rate * 1.5]
        sens_discount = [wacc * 0.8, wacc, wacc * 1.2]
        
        sensitivity_data = []
        
        for g in sens_growth:
            row = []
            for d in sens_discount:
                sens_result = dcf_valuation(
                    financial_data['fcf'], g, terminal_growth, d, 
                    years_projection, financial_data['shares_outstanding']
                )
                row.append(sens_result['intrinsic_value'] if sens_result else 0)
            sensitivity_data.append(row)
        
        sens_df = pd.DataFrame(
            sensitivity_data,
            index=[f"{g*100:.1f}%" for g in sens_growth],
            columns=[f"{d*100:.1f}%" for d in sens_discount]
        )
        
        st.dataframe(sens_df.style.format("${:.2f}").highlight_max(color='lightgreen').highlight_min(color='lightcoral'))
        
        # Explicación de los resultados
        with st.expander("Explicación del Método DCF"):
            st.markdown("""
            ### ¿Qué es el método DCF?
            El método de Flujo de Caja Descontado (DCF) es una técnica de valoración que utiliza 
            proyecciones de flujos de caja futuros y los descuenta a valor presente utilizando 
            una tasa de descuento apropiada.
            
            ### Componentes clave:
            1. *Flujo de Caja Libre (FCF)*: El efectivo que genera la empresa después de cubrir 
               sus gastos operativos y inversiones en capital.
            2. *Tasa de crecimiento*: La tasa a la que se espera que crezcan los flujos de caja 
               durante el período de proyección.
            3. *Tasa de descuento (WACC)*: La tasa utilizada para descontar los flujos de caja 
               futuros a valor presente. Representa el costo de oportunidad del capital.
            4. *Valor terminal*: El valor de la empresa más allá del período de proyección explícito, 
               calculado suponiendo una tasa de crecimiento perpetua.
            
            ### Fórmulas utilizadas:
            - *WACC*: = (E/V × Re) + (D/V × Rd × (1 - Tc))
            - *Valor presente de FCF*: = Σ [FCFₜ / (1 + WACC)ᵗ]
            - *Valor terminal*: = FCFₙ × (1 + g) / (WACC - g)
            - *Valor intrínseco por acción*: = (VP FCF + VP Terminal) / Acciones en circulación
            """)
    
    else:
        st.error("No se pudieron calcular los resultados del DCF. Verifique los datos financieros.")
        
elif financial_data and financial_data['fcf'] is None:
    st.error("No se pudo obtener el Flujo de Caja Libre (FCF) para esta empresa. Intenta con otro ticker.")
else:
    st.error(f"No se pudieron obtener datos para el ticker {ticker_symbol}. Verifique el símbolo e intente nuevamente.")

# Footer
st.markdown("---")
st.markdown("""
*Disclaimer*: Esta herramienta es solo con fines educativos e informativos. 
El valor intrínseco calculado se basa en supuestos y proyecciones que pueden no ser exactos. 
No constituye asesoramiento financiero. Siempre realice su propia investigación antes de tomar decisiones de inversión.
""")
