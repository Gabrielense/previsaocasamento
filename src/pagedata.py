#!/usr/bin/env python3
"""
Monta o data/page.json que o build.py injeta na pagina.

Separado do forecast_santa_maria.py de proposito: aquele script e o relatorio
que uma pessoa le no terminal, este e o contrato de dados da pagina. Os dois
usam as mesmas funcoes de coleta, entao nunca divergem.

O que e dinamico aqui e so o que realmente muda de um dia para o outro:

  - a data da rodada e quantos dias faltam
  - os 50 cenarios do SEAS5
  - a previsao determinstica, que so existe a partir de 15 dias
  - o veredito, que e derivado por regra dos numeros acima
  - a tabela de convergencia entre rodadas

A climatologia (os 42%, a grade de 35 anos, as curvas horarias) NAO entra
aqui. Sao 35 anos de medicao ja fechados: nao mudam nunca, entao ficam fixos
no template e nao gastam requisicao.

Uso:
    python src/pagedata.py --target 2026-10-03
"""

import argparse
import json
import os
import statistics as st
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import forecast_santa_maria as F  # noqa: E402

OUT = os.path.join(ROOT, "data", "page.json")

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ACC = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Nome curto de cada modelo, para a tabela da pagina.
NOMES = {
    "ecmwf_ifs025": ("ECMWF", "Europa"),
    "gfs_seamless": ("GFS", "NOAA/EUA"),
    "icon_seamless": ("ICON", "DWD/Alemanha"),
    "gem_seamless": ("GEM", "Canadá"),
    "ukmo_seamless": ("UKMO", "Reino Unido"),
    "meteofrance_seamless": ("Météo-France", "França"),
    "jma_seamless": ("JMA", "Japão"),
}
# Os quatro que a pagina mostra. Os outros tres entram so na dispersao, porque
# a tabela ficaria longa demais e eles raramente discordam dos quatro.
PRINCIPAIS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "gem_seamless"]


def _num(v):
    """Numero no padrao brasileiro, com virgula decimal."""
    return ("%.1f" % v).replace(".", ",")


def data_br(d):
    return "%d de %s de %d" % (d.day, MESES_ACC[d.month - 1], d.year)


def dia_mes(d):
    return "%d/%s" % (d.day, MESES[d.month - 1][:3])


# ---------------------------------------------------------------------------
# Veredito por regra
# ---------------------------------------------------------------------------
def veredito(lead, seas5, det, ens, clim_p_rain, dia_alvo="3 de outubro"):
    """Escreve o bloco de veredito a partir dos numeros, sem julgamento humano.

    Antes dos 15 dias a resposta e sempre a mesma, porque a fisica nao muda:
    nao existe previsao. Depois, o texto passa a depender de duas coisas
    mensuraveis: a probabilidade de chuva nos conjuntos e o quanto os modelos
    determinsticos concordam entre si.
    """
    # --- o dia chegou: a pagina para de prever e vira recado ----------------
    if lead == 0:
        hoje = []
        if det and det.get("blend"):
            b = det["blend"]
            pedaco = []
            if b.get("tmax") is not None:
                pedaco.append("máxima de <strong>%s °C</strong>" % _num(b["tmax"]))
            if ens.get("p_rain_1mm") is not None:
                pedaco.append("<strong>%d%% de chance de chuva</strong>" % ens["p_rain_1mm"])
            if b.get("gust") is not None:
                pedaco.append("rajada de até <strong>%d km/h</strong>" % round(b["gust"]))
            if pedaco:
                hoje.append("Para hoje os modelos dão " + ", ".join(pedaco) +
                            ". Seja o que for, agora é olhar pela janela e aproveitar.")
        return {
            "tom": "casamento",
            "headline": "Hoje é o dia. Parabéns aos dois!",
            "paras": hoje + [
                "Esta página passou dois meses dizendo que ninguém consegue prever um "
                "dia específico com antecedência. Chegou a hora em que isso deixa de "
                "importar: o tempo hoje é o tempo que vai fazer, e ele não muda mais "
                "com previsão nenhuma.",
                "Que seja um casamento lindo. <strong>Felicidades!</strong>",
            ],
        }

    # --- depois: a pagina fica parada, como lembranca -----------------------
    if lead < 0:
        return {
            "tom": "casamento",
            "headline": "O casamento foi em %s. Felicidades aos dois!" % dia_alvo,
            "paras": [
                "Esta página acompanhou a previsão do tempo por dois meses, de "
                "1º de agosto até o grande dia, e parou de se atualizar em "
                "%s. O que está aqui embaixo é o registro de como ficou." % dia_alvo,
            ],
        }

    if det is None:
        falta = lead - 15
        quando = "hoje" if falta <= 0 else ("amanhã" if falta == 1 else "em %d dias" % falta)
        return {
            "tom": "espera",
            "headline": ("A chance de chuva é de %d%%, e ninguém consegue dizer mais que "
                         "isso ainda. A previsão começa a valer %s." % (clim_p_rain, quando)),
            "paras": [
                "Faltam <strong>%d dias</strong>. Isso é mais que o alcance de qualquer "
                "modelo do mundo, então <strong>ninguém sabe</strong> se vai chover no dia 3 "
                "— e quem disser que sabe está mostrando média histórica com cara de "
                "previsão." % lead,
                "O número honesto de hoje vem dos 35 anos de medições: <strong>%d%% de "
                "chance de cair alguma chuva</strong> nesta data, e <strong>20%% de chance de "
                "ser chuva forte</strong>, acima de 10 mm. Ou seja: o mais provável é não "
                "chover, mas não é uma aposta confortável o bastante para dispensar "
                "cobertura." % clim_p_rain,
            ],
        }

    # --- dentro do alcance: o texto sai dos numeros --------------------------
    p = ens.get("p_rain_1mm")
    p10 = ens.get("p_rain_10mm")
    rains = [m["rain"] for m in det["models"] if m["rain"] is not None]
    spread = (max(rains) - min(rains)) if rains else 0.0
    concordam = spread <= 5.0
    gust = max([m["gust"] for m in det["models"] if m["gust"] is not None] or [0])

    if p is None:
        p = clim_p_rain

    # A comparacao com a climatologia so vale a pena quando os dois numeros
    # diferem o bastante para significar alguma coisa. Dizer "36%, perto dos
    # 36% de sempre" e ruido; dizer "o modelo nao esta vendo nada de diferente
    # do normal" e a mesma informacao, em portugues.
    dif = p - clim_p_rain
    if abs(dif) <= 5:
        ref = ("praticamente o mesmo de um %s comum, ou seja, os modelos ainda "
               "não estão vendo nada de diferente do normal" % dia_alvo)
    elif dif > 0:
        ref = "acima dos %d%% de um %s comum" % (clim_p_rain, dia_alvo)
    else:
        ref = "abaixo dos %d%% de um %s comum" % (clim_p_rain, dia_alvo)

    if p <= 25:
        tom, head = "bom", "Tende a não chover: %d%% de chance, %s." % (p, ref)
    elif p >= 60:
        tom, head = "ruim", ("Chuva provável: %d%% de chance, %s. Hora de acionar o "
                             "plano B." % (p, ref))
    else:
        tom, head = "neutro", "Ainda indefinido: %d%% de chance de chuva, %s." % (p, ref)

    quanto = ("Falta <strong>1 dia</strong>" if lead == 1
              else "Faltam <strong>%d dias</strong>" % lead)
    paras = [
        "%s, então o dia 3 já está dentro do alcance dos modelos e esta página passou "
        "a mostrar <strong>previsão de verdade</strong>, e não só média histórica." % quanto,
        "Os conjuntos dão <strong>%d%% de chance de chuva</strong> e <strong>%d%% de chance "
        "de chuva forte</strong>, acima de 10 mm." % (p, p10 if p10 is not None else 0),
    ]
    if concordam:
        paras.append(
            "E os modelos <strong>concordam entre si</strong>: a diferença entre o mais "
            "seco e o mais chuvoso é de apenas %s mm. Quando fontes independentes "
            "convergem assim, dá para confiar no sinal." % _num(spread))
    else:
        paras.append(
            "Mas os modelos <strong>ainda discordam</strong>: do mais seco ao mais chuvoso "
            "vão %s mm de diferença. Enquanto essa distância não encolher, o número "
            "acima ainda vai mudar." % _num(spread))
    if gust >= 40:
        paras.append(
            "Atenção ao <strong>vento</strong>: a maior rajada prevista é de %d km/h, o "
            "bastante para atrapalhar véu e penteado." % round(gust))
    return {"tom": tom, "headline": head, "paras": paras}


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=F.TARGET_DEFAULT)
    a = ap.parse_args()

    target = datetime.strptime(a.target, "%Y-%m-%d").date()
    today = date.today()
    lead = (target - today).days

    print("montando page.json  target=%s  run=%s  lead=%d" % (target, today, lead))

    clim = F.climatology(target)
    clim_p_rain = F.prob(clim["precip"], 1)

    # --- SEAS5: os 50 cenarios do grafico ------------------------------------
    seas5 = None
    s = F.seasonal(target)
    if s:
        pr = s["precipitation_sum"]
        seas5 = {
            "tmax": [round(x, 1) for x in s["temperature_2m_max"]],
            "tmin": [round(x, 1) for x in s["temperature_2m_min"]],
            "prec": [round(x, 1) for x in pr],
            "p_rain": F.prob(pr, 1),
            "n": len(pr),
        }
        print("  seas5: %d cenarios, P(chuva)=%s%%" % (seas5["n"], seas5["p_rain"]))

    # --- determinstico: so existe dentro do alcance --------------------------
    det = None
    if lead <= 15:
        rows = F.deterministic(target)
        if rows:
            models = []
            for k in PRINCIPAIS:
                r = rows.get(k) or {}
                if r.get("temperature_2m_max") is None:
                    continue
                nome, org = NOMES[k]
                models.append({
                    "key": k, "nome": nome, "org": org,
                    "tmax": r.get("temperature_2m_max"),
                    "tmin": r.get("temperature_2m_min"),
                    "rain": r.get("precipitation_sum"),
                    "gust": r.get("wind_gusts_10m_max"),
                })
            b = rows.get(F.BLEND_MODEL) or {}
            blend = None
            if b.get("temperature_2m_max") is not None:
                blend = {"nome": "Média combinada", "org": "blend multi-modelo",
                         "tmax": b.get("temperature_2m_max"),
                         "tmin": b.get("temperature_2m_min"),
                         "rain": b.get("precipitation_sum"),
                         "gust": b.get("wind_gusts_10m_max")}
            if models:
                def rng(f):
                    v = [m[f] for m in models if m[f] is not None]
                    return [min(v), max(v)] if v else None
                det = {"models": models, "blend": blend,
                       "spread": {"tmax": rng("tmax"), "rain": rng("rain"),
                                  "gust": rng("gust")}}
                print("  determin.: %d modelos" % len(models))

    # --- conjuntos: a probabilidade de chuva com muitos membros --------------
    ens = {}
    if lead <= 15:
        allp = []
        for m, b in (F.ensembles(target) or {}).items():
            allp += [x for x in b.get("precipitation_sum", []) if x is not None]
        if allp:
            ens = {"n": len(allp), "p_rain_1mm": F.prob(allp, 1),
                   "p_rain_5mm": F.prob(allp, 5), "p_rain_10mm": F.prob(allp, 10)}
            print("  conjuntos: %d membros, P(chuva)=%s%%" % (ens["n"], ens["p_rain_1mm"]))

    # --- convergencia entre rodadas -----------------------------------------
    conv = []
    if os.path.isdir(F.SNAPS):
        for fn in sorted(f for f in os.listdir(F.SNAPS) if f.startswith(target.isoformat())):
            try:
                sn = json.load(open(os.path.join(F.SNAPS, fn), encoding="utf-8"))
            except Exception:
                continue
            src = sn.get("seasonal") or (sn.get("ensemble") or {}).get("ecmwf_ifs025")
            if not src:
                continue
            conv.append({
                "run": sn["run_date"],
                "run_br": dia_mes(datetime.strptime(sn["run_date"], "%Y-%m-%d").date()),
                "lead": sn["lead_days"],
                "tmax": src["temperature_2m_max"]["median"],
                "rain_p": sn.get("seasonal_probs", {}).get("rain_ge_1mm"),
            })

    page = {
        "run_date": today.isoformat(),
        "run_br": data_br(today),
        "target": target.isoformat(),
        "lead_days": lead,
        "tier": "deterministico" if det else "sazonal",
        # A fase manda a pagina esconder o que deixou de fazer sentido: depois
        # que o dia chega, contagem regressiva e "o que mudou desde agosto"
        # viram ruido, e o que importa e o recado.
        "fase": ("depois" if lead < 0 else
                 "casamento" if lead == 0 else
                 "previsao" if det else "espera"),
        "encerrado": lead <= 0,
        "clim_p_rain": clim_p_rain,
        "veredito": veredito(lead, seas5, det, ens, clim_p_rain,
                             "%d de %s" % (target.day, MESES_ACC[target.month - 1])),
        "seas5": seas5,
        "det": det,
        "ens": ens,
        "convergencia": conv,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(page, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("gravado: %s  (tier=%s)" % (os.path.relpath(OUT, ROOT), page["tier"]))


if __name__ == "__main__":
    main()
