import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# ---------------- CONFIGURACIÓN PÁGINA ----------------
st.set_page_config(
    page_title="Calculadora DCF - Valor Intrínseco",
    page_icon="📈",
    layout="wide"
)

# ---------------- TÍTULO ----------------
st.title("📈 Calculadora de Valor Intrínseco - Método DCF")
st.markdown("""
Esta aplicación calcula el *valor intrínseco* de una acción utilizando el método de *Flujo de Caja Descontado (DCF)*.
""")

# ---------------- SIDEBAR ----------------
st.sidebar.header("Parámetros de Entrada")
ticker_symbol = st.sidebar.text_input("Símbolo del ticker", "AAPL").upper()
years_projection = st.sidebar.slider("Años de proyección", 5, 15, 10)
growth_rate = st.sidebar.slider("Tasa de crecimiento inicial (%)", 0.0, 20.0, 5.0) / 100
terminal_growth = st.sidebar.slider("Tasa de crecimiento terminal (%)", 0.0, 5.0, 2.5) / 100
discount_rate = st.sidebar.slider("Tasa de descuento (%)", 5.0, 15.0, 10.0) / 100


# ---------------- FUNCIÓN DATOS FINANCIEROS ----------------
@st.cache_data(ttl=3600)
def get_financial_data(ticker):
    try:
        stock = yf.Ticker(ticker)

        # Datos básicos
        info = stock.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 100.0)
        shares_outstanding = info.get("sharesOutstanding", 1_000_000)

        # Estimación inicial de FCF (5% del Market Cap)
        fcf = current_price * shares_outstanding * 0.05

        # Intentar calcular FCF desde cashflow
        try:
            cf = stock.cashflow
            if not cf.empty:
                if "Total Cash From Operating Activities" in cf.index and "Capital Expenditures" in cf.index:
                    op_cf = cf.loc["Total Cash From Operating Activities"].iloc[0]
                    capex = cf.loc["Capital Expenditures"].iloc[0]
                    if pd.notna(op_cf) and pd.notna(capex):
                        fcf = float(op_cf + capex)  # FCF = OCF - CAPEX
        except Exception:
            pass

        return {
            "current_price": float(current_price),
            "shares_outstanding": float(shares_outstanding),
            "fcf": float(fcf)
        }
    except Exception as e:
        st.error(f"Error obteniendo datos financieros: {e}")
        return None


# ---------------- FUNCIÓN DCF ----------------
def dcf_valuation(current_fcf, growth_rate, terminal_growth, discount_rate, years, shares):
    try:
        if current_fcf <= 0 or shares <= 0:
            return None
        if terminal_growth >= discount_rate:
            terminal_growth = discount_rate - 0.01

        future_cash_flows = [current_fcf * (1 + growth_rate) ** year for year in range(1, years + 1)]
        terminal_value = future_cash_flows[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)

        present_values = [fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(future_cash_flows)]
        terminal_pv = terminal_value / (1 + discount_rate) ** years

        enterprise_value = sum(present_values) + terminal_pv
        intrinsic_value = enterprise_value / shares

        return {
            "intrinsic_value": intrinsic_value,
            "enterprise_value": enterprise_value,
            "future_cash_flows": future_cash_flows,
            "present_values": present_values,
            "terminal_value": terminal_value
        }
    except Exception as e:
        st.error(f"Error en cálculo DCF: {e}")
        return None


# ---------------- LÓGICA PRINCIPAL ----------------
if st.sidebar.button("Calcular Valor Intrínseco"):
    data = get_financial_data(ticker_symbol)
    if data and data["current_price"] > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Información Básica")
            st.write(f"**Precio actual:** ${data['current_price']:.2f}")
            st.write(f"**Acciones en circulación:** {data['shares_outstanding']:,.0f}")
            st.write(f"**FCF estimado:** ${data['fcf']:,.0f}")

        results = dcf_valuation(
            current_fcf=data["fcf"],
            growth_rate=growth_rate,
            terminal_growth=terminal_growth,
            discount_rate=discount_rate,
            years=years_projection,
            shares=data["shares_outstanding"]
        )

        if results:
            with col2:
                st.subheader("Resultados DCF")
                st.metric("Valor intrínseco", f"${results['intrinsic_value']:.2f}")
                diff = results["intrinsic_value"] - data["current_price"]
                diff_pct = (diff / data["current_price"]) * 100
                st.metric("Diferencia con precio actual", f"${diff:.2f}", f"{diff_pct:.1f}%")

            # Gráfico
            years = list(range(1, years_projection + 1))
            fig = go.Figure()
            fig.add_trace(go.Bar(x=years, y=results["future_cash_flows"], name="FCF Proyectado"))
            fig.add_trace(go.Scatter(x=years, y=results["future_cash_flows"], name="Tendencia",
                                     line=dict(color="blue")))
            fig.update_layout(title="Proyección de Flujo de Caja Libre",
                              xaxis_title="Años", yaxis_title="FCF ($)")
            st.subheader("Proyección de Flujo de Caja Libre")
            st.plotly_chart(fig, use_container_width=True)

            # Tabla
            df = pd.DataFrame({
                "Año": years,
                "FCF Proyectado": [f"${x:,.0f}" for x in results["future_cash_flows"]],
                "Valor Presente": [f"${x:,.0f}" for x in results["present_values"]]
            })
            st.subheader("Desglose de la Valuación")
            st.dataframe(df, use_container_width=True)
            st.write(f"**Valor terminal:** ${results['terminal_value']:,.0f}")
            st.write(f"**Valor de la empresa:** ${results['enterprise_value']:,.0f}")
        else:
            st.error("Error en el cálculo DCF.")
    else:
        st.error("No se pudieron obtener datos financieros válidos.")

# ---------------- INFO ----------------
with st.expander("ℹ️ Acerca de este método"):
    st.markdown("""
    **Método DCF (Flujo de Caja Descontado)**

    - **FCF**: Flujo de Caja Libre
    - **Tasa de crecimiento**: Crecimiento anual proyectado
    - **Tasa de descuento**: Rentabilidad mínima esperada
    - **Crecimiento terminal**: Crecimiento perpetuo después del período proyectado

    **Fórmula simplificada:**
    - Valor = Σ [FCFₜ / (1 + r)ᵗ] + [FCFₙ × (1 + g) / (r - g)] / (1 + r)ⁿ
    """)

st.markdown("---")
st.caption("⚠️ Esta herramienta es solo con fines educativos. No constituye asesoramiento financiero.")
