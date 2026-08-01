# Previsão do tempo para 3 de outubro de 2026, Santa Maria/RS

Página estática que explica, para quem não entende de meteorologia, o que dá e o
que não dá para saber sobre o tempo no dia do casamento, e a partir de quando a
previsão passa a valer.

Local de referência: **-29,6842 / -53,8069** (Santa Maria, RS). Cerimônia às 17h30.

---

## Deploy na Vercel

O `index.html` fica na raiz e não depende de nada externo, então o deploy é sem
configuração alguma:

1. Em vercel.com, **Add New → Project** e importe este repositório.
2. Framework Preset: **Other**. Deixe build command e output directory vazios.
3. **Deploy**.

Não existe `vercel.json` porque não é preciso: a Vercel serve o `index.html` da
raiz automaticamente. Cada push na branch `main` republica o site.

### Por que a página é um arquivo só

O `index.html` tem 140 KB e faz **zero requisições de rede**. As fontes estão
embutidas como data URI e todos os dados estão no próprio JavaScript. Isso
significa que ele funciona offline, aberto direto do disco, e pode ser enviado
por e-mail como anexo único.

---

## Estrutura

```
index.html              página pronta, é o que a Vercel publica
src/
  template.html         fonte da página, com placeholders de fonte
  build.py              injeta as fontes e gera o index.html
  fonts/                3 arquivos .woff2 + licenças (SIL OFL 1.1)
forecast_santa_maria.py análise meteorológica semanal
snapshots/              histórico das execuções semanais
```

### Alterando a página

Edite `src/template.html`, nunca o `index.html` (ele é gerado e será
sobrescrito). Depois:

```bash
python src/build.py
```

---

## A análise, e como refazê-la toda semana

```bash
python forecast_santa_maria.py --target 2026-10-03 --compare
```

Só usa biblioteca padrão, não precisa de `pip install`. O script escolhe sozinho
a fonte certa conforme quanto falta para a data:

| Antecedência | O que ele usa | Período |
|---|---|---|
| mais de 15 dias | ECMWF SEAS5 sazonal, 50 cenários, mais climatologia | até 17/set/2026 |
| 15 dias ou menos | 6 modelos determinísticos, 3 conjuntos (119 membros), mais climatologia | 18/set a 3/out/2026 |

Cada execução grava `snapshots/2026-10-03_run_AAAA-MM-DD.json`. O `--compare`
imprime a tabela de convergência, que mostra se o sinal está se firmando:

```
run          lead  Tmax med  Tmin med  Rain med  P>=1mm
2026-08-01     63      21.3      12.6       0.7      46
```

A climatologia do ERA5 fica em cache na primeira execução, então as seguintes
levam segundos.

### Rotina sugerida

1. Rode o script e anote a linha.
2. Confira o boletim de El Niño do CPC, atualizado toda segunda quinta-feira.
3. A partir de **18 de setembro**, passe a olhar o bloco determinístico. Observe
   a **dispersão entre modelos**, não a média: quando ECMWF, GFS, ICON e UKMO
   convergirem dentro de uns 2 °C e 5 mm, o sinal é real.
4. A partir de **29 de setembro** a previsão vira acionável. Cruze com os
   alertas do INMET.

---

## O que os dados dizem hoje (1º de agosto de 2026)

**Antecedência de 63 dias.** A previsibilidade determinística da atmosfera acaba
por volta de 10 a 15 dias. Nenhuma fonte no mundo consegue dizer o tempo do dia 3
de outubro hoje. O que existe é uma distribuição de probabilidade.

### Climatologia observada, ERA5 1991 a 2025, 3/out ± 5 dias (n = 385)

| Variável | média | p10 | p25 | mediana | p75 | p90 | mín | máx |
|---|---|---|---|---|---|---|---|---|
| Tmax (°C) | 22,3 | 18,0 | 19,7 | 21,7 | 24,3 | 28,1 | 13,4 | 36,5 |
| Tmin (°C) | 12,8 | 8,2 | 10,2 | 12,7 | 15,4 | 17,3 | 2,7 | 23,1 |
| Chuva (mm/dia) | 6,4 | 0,0 | 0,0 | 0,2 | 6,8 | 20,9 | 0,0 | 126,4 |

```
P(chuva >=  1 mm) = 42,3%      P(Tmax >= 25 °C) = 23,1%
P(chuva >=  5 mm) = 27,3%      P(Tmax >= 30 °C) =  4,7%
P(chuva >= 10 mm) = 20,3%      P(Tmin <= 10 °C) = 23,9%
P(chuva >= 30 mm) =  5,2%      P(Tmin <=  7 °C) =  4,7%
```

**Tendência de aquecimento na janela**, que puxa a média de 35 anos para baixo:

| Período | Tmax | Tmin | Chuva/dia |
|---|---|---|---|
| 1991 a 2005 | 21,72 °C | 12,55 °C | 7,59 mm |
| 2006 a 2015 | 22,47 °C | 12,63 °C | 4,43 mm |
| 2016 a 2025 | **23,10 °C** | **13,29 °C** | 6,50 mm |

A máxima subiu **1,38 °C** entre o primeiro e o último período, então use a
última década, não a média completa.

### ECMWF SEAS5, 50 membros, rodada de 1º/08/2026

| Variável | média | p25 | mediana | p75 | mín | máx |
|---|---|---|---|---|---|---|
| Tmax (°C) | 21,6 | 18,1 | 21,3 | 25,3 | 13,6 | 29,0 |
| Tmin (°C) | 13,0 | 10,7 | 12,6 | 15,1 | 6,6 | 19,6 |
| Chuva (mm) | 5,8 | 0,0 | 0,7 | 4,5 | 0,0 | 61,8 |

`P(chuva ≥1 mm) = 46%` · `P(≥5 mm) = 22%` · `P(≥10 mm) = 16%`

O SEAS5 é estatisticamente indistinguível da climatologia (mediana de Tmax 21,3
contra 21,7; chuva 46% contra 42%). O modelo **não carrega sinal utilizável**
para esta data, que é o resultado esperado e correto a 63 dias.

### El Niño, o único sinal real disponível

- **NOAA CPC, boletim de 9 de julho de 2026: alerta de El Niño em vigor.**
- Anomalia de Niño-3.4 mais recente: **+1,2 °C**.
- **81% de chance de El Niño muito forte entre outubro e dezembro de 2026.**
- Julho de 2026 fechou com **276,3 mm em Santa Maria contra 144,9 mm de um julho
  comum, ou 191% do normal** (calculado do ERA5 neste repositório).

**Totais de outubro em Santa Maria (ERA5):** média geral 203,1 mm; média em anos
de El Niño 240,1 mm, ou 18% a mais. O agregado esconde o essencial: o sinal está
nos eventos **fortes**.

| Ano | Total de outubro | Intensidade do El Niño |
|---|---|---|
| 1997 | **551,9 mm** | muito forte |
| 2002 | **422,4 mm** | moderado a forte |
| 2023 | **346,1 mm** | forte |
| 2004 | 144,2 mm | fraco |
| 2009 | 99,6 mm | fraco a moderado |
| 2018 | 84,5 mm | fraco |

Anos de El Niño fraco não mostram sinal nenhum de chuva. Dado o prognóstico de
evento muito forte, os análogos relevantes são 1997, 2002 e 2023.

### Conclusão factual para o dia 3

1. **Não existe previsão determinística.** A primeira orientação com skill real
   chega por volta de **18 de setembro de 2026**.
2. **Melhor estimativa hoje é climatológica, ajustada pela tendência:** máxima
   perto de **23 °C** (faixa provável 19 a 26), mínima perto de **13 °C** (10 a
   16), probabilidade de chuva mensurável de cerca de **45%**.
3. **O sinal mensal é muito mais forte que o diário.** Outubro de 2026 tende a
   ser mais chuvoso que os 203 mm normais, por causa do El Niño. Isso não diz
   nada confiável sobre o dia 3.
4. **Cauda pesada.** Em outubros de El Niño forte a cauda de chuva intensa
   engorda. Os 5,2% climatológicos de `P(≥30 mm/dia)` são um piso, não uma
   estimativa central.

---

## Fontes

Três fontes produziram todos os números acima e da página:

| Fonte | O que veio dela | Endpoint |
|---|---|---|
| **ERA5** (Copernicus/ECMWF) | climatologia, grade dos 35 anos, curva horária, totais de outubro, julho de 2026 | `archive-api.open-meteo.com` |
| **ECMWF SEAS5** | os 50 cenários, e só isso | `seasonal-api.open-meteo.com` |
| **NOAA CPC** | estado do El Niño e os 81% | `cpc.ncep.noaa.gov` |

Estas **não** geraram número algum aqui, porque hoje não teriam o que informar
sobre o dia 3. Passam a ser as principais a partir de 18 de setembro:

| Fonte | Para quê | Endereço |
|---|---|---|
| **INMET** | previsão oficial e alertas com valor legal; estação A803 | `previsao.inmet.gov.br/4316907` |
| **CPTEC/INPE** | modelos brasileiros, para comparar | `tempo.cptec.inpe.br` |
| **MetSul** | leitura interpretada para o RS | `metsul.com` |

> **Nota sobre a API do INMET.** O endpoint `apitempo.inmet.gov.br/estacao/...`
> devolveu resposta vazia (HTTP 204) para todas as datas testadas, inclusive
> históricas. O endpoint de lista de estações funciona e confirma a A803 como
> operante. Ou seja, o INMET não é utilizável de forma automatizada no momento;
> use a tabela web ou o BDMEP, e o ERA5 para qualquer coisa programática.

---

## Licenças

Fontes Quicksand e Lato sob SIL Open Font License 1.1, ver
[`src/fonts/LICENSES.md`](src/fonts/LICENSES.md). Dados do ERA5 e do SEAS5 via
[Open-Meteo](https://open-meteo.com), sob CC BY 4.0.
