import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(
    page_title="Calculadora DCF - Valor Intrínseco",
    page_icon="📈",
    layout="wide"
)

# Título de la aplicación
st.title("📈 Calculadora de Valor Intrínseco - Método DCF")
st.markdown("""
Esta aplicación calcula el *valor intrínseco* de una acción utilizando el método de *Flujo de Caja Descontado (DCF)*.
""")

# Sidebar para inputs
st.sidebar.header("Parámetros de Entrada")
ticker_symbol = st.sidebar.text_input("Símbolo del ticker", "AAPL").upper()
years_projection = st.sidebar.slider("Años de proyección", 5, 15, 10)
growth_rate = st.sidebar.slider("Tasa de crecimiento inicial (%)", 0.0, 20.0, 5.0) / 100
terminal_growth = st.sidebar.slider("Tasa de crecimiento terminal (%)", 0.0, 5.0, 2.5) / 100
discount_rate = st.sidebar.slider("Tasa de descuento (%)", 5.0, 15.0, 10.0) / 100

# Función para obtener datos financieros
@st.cache_data(ttl=3600)
def get_financial_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Obtener datos básicos con múltiples opciones
        current_price = info.get('currentPrice', 
                               info.get('regularMarketPrice', 
                                       info.get('previousClose', 100)))
        
        shares_outstanding = info.get('sharesOutstanding', 
                                    info.get('floatShares', 
                                            info.get('sharesOutstanding', 1000000)))
        
        # Obtener FCF de forma robusta
        fcf = 0
        try:
            # Obtener cash flow statements
            cash_flow = stock.cashflow
            if not cash_flow.empty:
                # Buscar Free Cash Flow en diferentes formatos posibles
                possible_fcf_names = [
                    'Free Cash Flow', 'FreeCashFlow', 'Free cash flow',
                    'Operating Cash Flow', 'Cash Flow from Operations'
                ]
                
                for fcf_name in possible_fcf_names:
                    if fcf_name in cash_flow.index:
                        fcf_value = cash_flow.loc[fcf_name]
                        if not fcf_value.empty:
                            fcf = float(fcf_value.iloc[0])
                            break
                
                # Si no encontramos FCF, usar estimación basada en market cap
                if fcf == 0:
                    fcf = current_price * shares_outstanding * 0.05
                    
        except Exception as e:
            st.warning(f"No se pudo obtener FCF detallado: {e}")
            fcf = current_price * shares_outstanding * 0.05
        
        return {
            'current_price': float(current_price),
            'shares_outstanding': float(shares_outstanding),
            'fcf': float(fcf),
            'info': info
        }
    except Exception as e:
        st.error(f"Error obteniendo datos: {str(e)}")
        return None

# Función DCF simplificada
def dcf_valuation(current_fcf, growth_rate, terminal_growth, discount_rate, years, shares):
    try:
        # Validar inputs
        if current_fcf <= 0 or shares <= 0:
            return None
            
        # Asegurar que la tasa terminal sea menor que la de descuento
        if terminal_growth >= discount_rate:
            terminal_growth = discount_rate - 0.01
        
        # Proyectar flujos de caja futuros
        future_cash_flows = []
        for year in range(1, years + 1):
            future_fcf = current_fcf * (1 + growth_rate) ** year
            future_cash_flows.append(future_fcf)
        
        # Calcular valor terminal
        terminal_value = future_cash_flows[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        
        # Descontar flujos de caja
        present_values = []
        for i, fcf in enumerate(future_cash_flows):
            pv = fcf / (1 + discount_rate) ** (i + 1)
            present_values.append(pv)
        
        # Descontar valor terminal
        terminal_pv = terminal_value / (1 + discount_rate) ** years
        
        # Valor total
        enterprise_value = sum(present_values) + terminal_pv
        intrinsic_value = enterprise_value / shares
        
        return {
            'intrinsic_value': intrinsic_value,
            'enterprise_value': enterprise_value,
            'current_fcf': current_fcf,
            'present_values': present_values,
            'future_cash_flows': future_cash_flows,
            'terminal_value': terminal_value
        }
    except Exception as e:
        st.error(f"Error en cálculo DCF: {str(e)}")
        return None

# Main app logic
if st.sidebar.button("Calcular Valor Intrínseco"):
    if ticker_symbol:
        with st.spinner('Obteniendo datos y calculando...'):
            financial_data = get_financial_data(ticker_symbol)
            
            if financial_data and financial_data['current_price'] > 0:
                # Mostrar información básica
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Información Básica")
                    st.write(f"**Precio actual:** ${financial_data['current_price']:.2f}")
                    st.write(f"**Acciones en circulación:** {financial_data['shares_outstanding']:,.0f}")
                    st.write(f"**FCF estimado:** ${financial_data['fcf']:,.0f}")
                
                # Calcular valuación
                results = dcf_valuation(
                    current_fcf=financial_data['fcf'],
                    growth_rate=growth_rate,
                    terminal_growth=terminal_growth,
                    discount_rate=discount_rate,
                    years=years_projection,
                    shares=financial_data['shares_outstanding']
                )
                
                if results:
                    with col2:
                        st.subheader("Resultados DCF")
                        st.metric("Valor intrínseco", f"${results['intrinsic_value']:.2f}")
                        
                        diferencia = results['intrinsic_value'] - financial_data['current_price']
                        diferencia_porcentaje = (diferencia / financial_data['current_price']) * 100
                        st.metric("Diferencia con precio actual", 
                                 f"${diferencia:.2f}", 
                                 f"{diferencia_porcentaje:.1f}%")
                        
                        # Recomendación
                        if results['intrinsic_value'] > financial_data['current_price'] * 1.2:
                            rec = "FUERTE COMPRA 🚀"
                            color = "green"
                        elif results['intrinsic_value'] > financial_data['current_price']:
                            rec = "COMPRA ✅"
                            color = "lightgreen"
                        elif results['intrinsic_value'] > financial_data['current_price'] * 0.8:
                            rec = "MANTENER ⚖️"
                            color = "orange"
                        else:
                            rec = "VENDE 🔴"
                            color = "red"
                            
                        st.markdown(f"### **Recomendación:** <span style='color:{color}'>{rec}</span>", 
                                   unsafe_allow_html=True)
                    
                    # Gráfico de proyección
                    st.subheader("Proyección de Flujo de Caja Libre")
                    years = list(range(1, years_projection + 1))
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=years,
                        y=results['future_cash_flows'],
                        name="FCF Proyectado",
                        marker_color='lightblue'
                    ))
                    fig.add_trace(go.Scatter(
                        x=years,
                        y=results['future_cash_flows'],
                        name="Tendencia",
                        line=dict(color='blue', width=2)
                    ))
                    
                    fig.update_layout(
                        title="Proyección de Flujo de Caja Libre",
                        xaxis_title="Años",
                        yaxis_title="FCF ($)",
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tabla de resultados
                    st.subheader("Desglose de la Valuación")
                    breakdown_data = {
                        'Año': years,
                        'FCF Proyectado': [f"${x:,.0f}" for x in results['future_cash_flows']],
                        'Valor Presente': [f"${x:,.0f}" for x in results['present_values']]
                    }
                    
                    breakdown_df = pd.DataFrame(breakdown_data)
                    st.dataframe(breakdown_df, use_container_width=True)
                    
                    st.write(f"**Valor terminal:** ${results['terminal_value']:,.0f}")
                    st.write(f"**Valor de la empresa:** ${results['enterprise_value']:,.0f}")
                    
                else:
                    st.error("Error en el cálculo DCF. Revisa los parámetros.")
            else:
                st.error("No se pudieron obtener datos financieros válidos. Verifica el símbolo del ticker.")
    else:
        st.warning("Por favor ingresa un símbolo de ticker válido")

# Información adicional
with st.expander("ℹ️ Acerca de este método"):
    st.markdown("""
    **Método DCF (Flujo de Caja Descontado)**
    
    - **FCF**: Flujo de Caja Libre estimado
    - **Tasa de crecimiento**: Crecimiento anual proyectado del FCF
    - **Tasa de descuento**: Rentabilidad mínima esperada
    - **Crecimiento terminal**: Crecimiento perpetuo después del período de proyección
    
    **Fórmula simplificada:**
    - Valor = Σ [FCFₜ / (1 + r)ᵗ] + [FCFₙ × (1 + g) / (r - g)] / (1 + r)ⁿ
    """)

# Footer
st.markdown("---")
st.caption("""
⚠️ **Disclaimer**: Esta herramienta es solo con fines educativos. 
No constituye asesoramiento financiero. Siempre realiza tu propia investigación.
""")
