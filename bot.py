import os
from datetime import datetime, timedelta, date
import numpy as np
import pandas as pd
import yfinance as yf         
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
import requests
import matplotlib.pyplot as plt
import time

# Forzar a matplotlib a correr en modo headless (servidor sin pantalla)
plt.switch_backend('Agg')

# ==============================================================================
# CONFIGURACIÓN DE PRODUCCIÓN (Lista Filtrada a 27 Emisoras)
# ==============================================================================
CONFIG = {
    "assets": [
        "AMXB.MX", "WALMEX.MX", "FEMSAUBD.MX", "GAPB.MX", "FUNO11.MX", 
        "GRUMAB.MX", "CHDRAUIB.MX", "KOFUBL.MX", "OMAB.MX", "GENTERA.MX", 
        "BBAJIOO.MX", "CUERVO.MX", "SITES1A-1.MX", "RA.MX", "ORBIA.MX", 
        "ALSEA.MX", "MEGACPO.MX", "LASITE.MX", "TLEVISACPO.MX", "ALPEKA.MX", 
        "HERDEZ.MX", "LIVEPOLC-1.MX", "FCFE18.MX", "NEMAKA.MX", "AXTELCPO.MX", 
        "FIHO12.MX", "ARA.MX"
    ], 
    "dend": date.today().strftime('%Y-%m-%d'),  
    "modo_pruebas": False, # Cambiar a False cuando desees operar en vivo con mercado real
    "ema_f": 20,
    "ema_s": 50,
    "rsi_pr": 14,
    "rsi_buy": 55,
    "rsi_sell": 45,
    "atr_pr": 14,
    "sl_mult": 1.5,
    "tp_mult": 2.5,
    "vol_pr": 20,
    "telegram_token": os.environ.get('TELEGRAM_TOKEN'),
    "telegram_chat_id": os.environ.get('TELEGRAM_CHAT_ID')
}

# ==============================================================================
# MOTOR DEL SISTEMA
# ==============================================================================
def generar_y_guardar_grafico(df, cfg, ticker, last_index, precio_entrada=None, sl=None, tp=None):
    df_plot = df.iloc[max(0, last_index-40):last_index+2].copy()
    
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), gridspec_kw={'height_ratios': [3, 1]})
    
    # Panel Superior: Velas Japonesas, EMAs y Bandas de Bollinger
    inc = df_plot['askclose'] >= df_plot['askopen']
    dec = df_plot['askopen'] > df_plot['askclose']
    c_up, c_down = '#2ca02c', '#d62728'
    
    # Velas (Mechas y Cuerpos)
    ax1.vlines(df_plot['Date'][inc], df_plot['asklow'][inc], df_plot['askhigh'][inc], color=c_up, linewidth=1.2, zorder=3)
    ax1.vlines(df_plot['Date'][dec], df_plot['asklow'][dec], df_plot['askhigh'][dec], color=c_down, linewidth=1.2, zorder=3)
    ax1.bar(df_plot['Date'][inc], df_plot['askclose'][inc] - df_plot['askopen'][inc], bottom=df_plot['askopen'][inc], color=c_up, width=0.5, zorder=4)
    ax1.bar(df_plot['Date'][dec], df_plot['askopen'][dec] - df_plot['askclose'][dec], bottom=df_plot['askclose'][dec], color=c_down, width=0.5, zorder=4)
    
    # Líneas de Tendencia (EMAs)
    ax1.plot(df_plot['Date'], df_plot['ema20'], label=f'EMA {cfg["ema_f"]}', color='#ff7f0e', linestyle='--', linewidth=1.5, zorder=5)
    ax1.plot(df_plot['Date'], df_plot['ema50'], label=f'EMA {cfg["ema_s"]}', color='#1f77b4', linestyle='--', linewidth=1.5, zorder=5)
    
    # Bandas de Bollinger (Apoyo Visual)
    ax1.plot(df_plot['Date'], df_plot['bb_hband'], color='#7f7f7f', linestyle=':', alpha=0.4, label='Bollinger (20, 2)', zorder=2)
    ax1.plot(df_plot['Date'], df_plot['bb_lband'], color='#7f7f7f', linestyle=':', alpha=0.4, zorder=2)
    ax1.fill_between(df_plot['Date'], df_plot['bb_lband'], df_plot['bb_hband'], color='#7f7f7f', alpha=0.03, zorder=1)

    # Niveles de Riesgo ATR (Zonas Sombreadas)
    if precio_entrada is not None and sl is not None and tp is not None:
        ax1.axhline(precio_entrada, color='#4B0082', linestyle='-', linewidth=1.2, label=f'Entrada ({precio_entrada:.2f})', zorder=6)
        ax1.axhline(sl, color='#d62728', linestyle='-', linewidth=1.5, label=f'Stop Loss ({sl:.2f})', zorder=6)
        ax1.axhline(tp, color='#2ca02c', linestyle='-', linewidth=1.5, label=f'Take Profit ({tp:.2f})', zorder=6)
        ax1.axhspan(precio_entrada, tp, color='#2ca02c', alpha=0.07, zorder=0, label='Zona Objetivo')
        ax1.axhspan(sl, precio_entrada, color='#d62728', alpha=0.07, zorder=0, label='Zona Riesgo')

    ax1.set_title(f"{ticker}", fontsize=14, fontweight='bold')
    ax1.set_ylabel('Precio')
    
    # Panel Inferior: RSI
    ax2.plot(df_plot['Date'], df_plot['rsi'], color='#9467bd', linewidth=1.8, label='RSI (14)')
    ax2.axhline(cfg['rsi_buy'], color='#d62728', linestyle=':', alpha=0.8)
    ax2.axhline(cfg['rsi_sell'], color='#1f77b4', linestyle=':', alpha=0.8)
    ax2.set_ylim(15, 85)
    ax2.set_ylabel('RSI')
    
    # Leyenda unificada posicionada abajo
    handles, labels = ax1.get_legend_handles_labels()
    ax2.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.35), ncol=3, frameon=True, facecolor='white', framealpha=0.95, fontsize=8.5)
    
    plt.xticks(rotation=25)
    plt.tight_layout()
    
    ruta_imagen = f'alerta_{ticker}.png'
    plt.savefig(ruta_imagen, dpi=150, bbox_inches='tight')
    plt.close()
    return ruta_imagen

def despachar_telegram_con_foto(token, chat_id, mensaje, ruta_foto):
    if not token or not chat_id:
        print(f"⚠️ Credenciales ausentes. Falló despacho de:\n{mensaje}")
        return
    url = f'https://api.telegram.org/bot{token}/sendPhoto'
    try:
        with open(ruta_foto, 'rb') as foto:
            payload = {'chat_id': chat_id, 'caption': mensaje, 'parse_mode': 'Markdown'}
            res = requests.post(url, data=payload, files={'photo': foto})
            print(f"📸 Telegram despachado para {ruta_foto}. Status: {res.status_code}")
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")

def despachar_telegram_texto(token, chat_id, mensaje):
    if not token or not chat_id:
        print(f"⚠️ Credenciales ausentes. Texto en consola:\n{mensaje}")
        return
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        res = requests.post(url, json={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'Markdown'})
        print(f"📋 Notificación de control de workflow enviada. Status: {res.status_code}")
    except Exception as e:
        print(f"❌ Error enviando resumen a Telegram: {e}")

def ejecutar_escanner(cfg):
    # Variables de control e indicadores globales del proceso
    fecha_operacion = datetime.strptime(cfg['dend'], "%Y-%m-%d").strftime('%Y/%m/%d')
    conteo_compra = 0
    conteo_venta = 0

    # ==========================================================================
    # MODIFICACIÓN: SIMULACIÓN FIEL CON VELAS Y REPORTE COMPLETO AL FINAL
    # ==========================================================================
    if cfg['modo_pruebas']:
        print(f"🧪 [MODO PRUEBA MULTI-ACTIVO] Generando simulaciones fieles con velas para: {cfg['assets']}\n")
        
        for idx, ticker in enumerate(cfg['assets']):
            precio_base = 45.0 + (idx * 15.0)  
            fechas_mock = [datetime.now() - timedelta(days=x) for x in range(50, -1, -1)]
            
            close_mock = np.linspace(precio_base, precio_base * 1.15, 51) + np.random.normal(0, 1, 51)
            open_mock = np.roll(close_mock, 1)
            open_mock[0] = precio_base
            high_mock = np.maximum(close_mock, open_mock) + np.abs(np.random.normal(0, 1.2, 51))
            low_mock = np.minimum(close_mock, open_mock) - np.abs(np.random.normal(0, 1.2, 51))
            
            df = pd.DataFrame({
                'Date': fechas_mock, 
                'askclose': close_mock,
                'askopen': open_mock,
                'askhigh': high_mock,
                'asklow': low_mock
            })
            df['Volume'] = np.random.randint(150000, 450000, 51)
            
            df['ema20'] = df['askclose'] - 1.5
            df['ema50'] = df['askclose'] - 4.5
            df['rsi'] = np.linspace(42, 57, 51) 
            df['atr'] = round(precio_base * 0.03, 2)
            df['bb_hband'] = df['askclose'] + (precio_base * 0.06)
            df['bb_lband'] = df['askclose'] - (precio_base * 0.06)
            
            last_index = df.index[-2]
            precio_simulado = round(df['askclose'].iloc[last_index], 2)
            atr_mock = df['atr'].iloc[last_index]
            
            sl_simulado = round(precio_simulado - (cfg['sl_mult'] * atr_mock), 2)
            tp_simulado = round(precio_simulado + (cfg['tp_mult'] * atr_mock), 2)
            
            ruta = generar_y_guardar_grafico(df, cfg, ticker, last_index, precio_simulado, sl_simulado, tp_simulado)
            
            msg_test = (f"🧪 **ALERTA SIMULADA ({ticker})**\n\n"
                        f"🟢 **ENTRADA LONG GATILLADA**\n"
                        f"📅 Fecha: {cfg['dend']} (Hoy)\n"
                        f"💰 Precio Entrada: {precio_simulado}\n"
                        f"🛑 Stop Loss (1.5x ATR): {sl_simulado}\n"
                        f"🎯 Take Profit (2.5x ATR): {tp_simulado}")
            
            despachar_telegram_con_foto(cfg['telegram_token'], cfg['telegram_chat_id'], msg_test, ruta)
            conteo_compra += 1  # Forzamos conteo de test
            time.sleep(0.5)
            
        # Reporte obligatorio final para Modo Pruebas
        total_test = conteo_compra + conteo_venta
        msg_resumen_test = (f"🧪 **Ejecución correcta del workflow (MODO PRUEBA)**\n"
                            f"📅 Fecha: {fecha_operacion}\n"
                            f"📊 Total señales: {total_test}\n"
                            f"🟩 De compra: {conteo_compra}\n"
                            f"🟥 De venta: {conteo_venta}")
        despachar_telegram_texto(cfg['telegram_token'], cfg['telegram_chat_id'], msg_resumen_test)
        return

    # ==========================================================================
    # EJECUCIÓN REAL EN MERCADO PROTEGIDA CON CONTROL TOTAL DE FIN DE RUN
    # ==========================================================================
    try:
        print(f"🔍 Iniciando escaneo de mercado real para {len(cfg['assets'])} activos...\n")
        
        for ticker in cfg['assets']:
            try:
                dias_atras = int((cfg['ema_s'] + cfg['vol_pr'] + 15) * 7 / 5)
                dini = (datetime.strptime(cfg['dend'], "%Y-%m-%d") - timedelta(days=dias_atras)).strftime('%Y-%m-%d')
                df = yf.download(ticker, start=dini, end=cfg['dend'], auto_adjust=True, progress=False)
                
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                df.rename(columns={'Open':'askopen', 'High':'askhigh', 'Low':'asklow', 'Close':'askclose'}, inplace=True)
                df.reset_index(inplace=True)

                # Indicadores Técnicos
                df['ema20'] = EMAIndicator(df['askclose'].squeeze(), cfg['ema_f']).ema_indicator()
                df['ema50'] = EMAIndicator(df['askclose'].squeeze(), cfg['ema_s']).ema_indicator()
                df['rsi'] = RSIIndicator(df['askclose'].squeeze(), cfg['rsi_pr']).rsi()
                df['atr'] = AverageTrueRange(df['askhigh'].squeeze(), df['asklow'].squeeze(), df['askclose'].squeeze(), cfg['atr_pr']).average_true_range()
                df['vol_sma'] = df['Volume'].rolling(cfg['vol_pr']).mean()

                bb_indicator = BollingerBands(df['askclose'].squeeze(), window=20, window_dev=2)
                df['bb_hband'] = bb_indicator.bollinger_hband()
                df['bb_lband'] = bb_indicator.bollinger_lband()

                # Condiciones
                df['cond_trend'] = (df['ema20'] > df['ema50']) & (df['askclose'] > df['ema20'])
                df['cond_rsi_buy'] = (df['rsi'] >= cfg['rsi_buy']) & (df['rsi'].shift(1) < cfg['rsi_buy'])
                df['cond_vol'] = df['Volume'] > df['vol_sma']
                df['signal_long'] = df['cond_trend'] & df['cond_rsi_buy'] & df['cond_vol']
                df['exit_indicators'] = (df['rsi'] < cfg['rsi_sell']) | (df['askclose'] < df['ema20'])

                last_index = df.index[-1]
                posicion_activa, entry_idx = False, None

                for i in range(max(0, last_index - 30), last_index + 1):
                    if df['signal_long'].iloc[i]: posicion_activa, entry_idx = True, i
                    elif posicion_activa and df['exit_indicators'].iloc[i]: posicion_activa, entry_idx = False, None

                precio_cierre = round(df['askclose'].iloc[last_index], 4)
                fecha_str = pd.to_datetime(df['Date'].iloc[last_index]).strftime('%Y/%m/%d')
                df['Alerta'] = ' Neutral'

                # Despacho de Compra (LONG)
                if df['signal_long'].iloc[last_index]:
                    df.loc[last_index, 'Alerta'] = '🟢 COMPRA'
                    conteo_compra += 1
                    sl = round(precio_cierre - (cfg['sl_mult'] * df['atr'].iloc[last_index]), 4)
                    tp = round(precio_cierre + (cfg['tp_mult'] * df['atr'].iloc[last_index]), 4)
                    ruta = generar_y_guardar_grafico(df, cfg, ticker, last_index, precio_cierre, sl, tp)
                    msg = f"🟢 **COMPRA ({ticker})**\n📅 {fecha_str}\n💰 Entrada: {precio_cierre}\n🛑 SL: {sl}\n🎯 TP: {tp}"
                    despachar_telegram_con_foto(cfg['telegram_token'], cfg['telegram_chat_id'], msg, ruta)
                    
                # Despacho de Ventas/Salidas Activas
                elif posicion_activa and entry_idx is not None:
                    p_entry = df['askclose'].iloc[entry_idx]
                    atr_e = df['atr'].iloc[entry_idx]
                    sl, tp = p_entry - (cfg['sl_mult'] * atr_e), p_entry + (cfg['tp_mult'] * atr_e)

                    if precio_cierre <= sl:
                        df.loc[last_index, 'Alerta'] = '🔴 HIT SL'
                        conteo_venta += 1
                        ruta = generar_y_guardar_grafico(df, cfg, ticker, last_index, p_entry, sl, tp)
                        despachar_telegram_con_foto(cfg['telegram_token'], cfg['telegram_chat_id'], f"🔴 **HIT SL ({ticker})**\n📉 Salida: {precio_cierre}", ruta)
                    elif precio_cierre >= tp:
                        df.loc[last_index, 'Alerta'] = '🟢 HIT TP'
                        conteo_venta += 1
                        ruta = generar_y_guardar_grafico(df, cfg, ticker, last_index, p_entry, sl, tp)
                        despachar_telegram_con_foto(cfg['telegram_token'], cfg['telegram_chat_id'], f"🟢 **HIT TP ({ticker})**\n📈 Salida: {precio_cierre}", ruta)
                    elif df['exit_indicators'].iloc[last_index]:
                        df.loc[last_index, 'Alerta'] = '⚠️ EXIT TEC'
                        conteo_venta += 1
                        ruta = generar_y_guardar_grafico(df, cfg, ticker, last_index, p_entry, sl, tp)
                        despachar_telegram_con_foto(cfg['telegram_token'], cfg['telegram_chat_id'], f"⚠️ **EXIT TÉCNICO ({ticker})**\n📉 Salida: {precio_cierre}", ruta)
                
                print(f"📊 Estado {ticker} -> Precio: {precio_cierre:.2f} | Alerta: {df['Alerta'].iloc[last_index]}")
                time.sleep(0.5)
            except Exception as e_asset:
                print(f"🚨 Error individual saltado para {ticker}: {e_asset}")
                continue

        # --- NOTIFICACIÓN EXCELENTE: FIN DE WORKFLOW EXITOSO ---
        total_señales = conteo_compra + conteo_venta
        msg_exito = (f"✅ **Ejecución correcta del workflow**\n"
                     f"📅 Fecha: {fecha_operacion}\n"
                     f"📊 Total señales: {total_señales}\n"
                     f"🟩 De compra: {conteo_compra}\n"
                     f"🟥 De venta: {conteo_venta}")
        print(f"\n{msg_exito}")
        despachar_telegram_texto(cfg['telegram_token'], cfg['telegram_chat_id'], msg_exito)

    except Exception as e_critico:
        # --- NOTIFICACIÓN EN CASO DE COLAPSO GENERAL DEL SISTEMA ---
        msg_fallo = (f"🚨 **Error en la ejecución del workflow**\n"
                     f"📅 Fecha: {fecha_operacion}\n"
                     f"❌ Detalle técnico: `{str(e_critico)}`")
        print(f"\n{msg_fallo}")
        despachar_telegram_texto(cfg['telegram_token'], cfg['telegram_chat_id'], msg_fallo)

if __name__ == "__main__":
    ejecutar_escanner(CONFIG)
