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

O `index.html` tem 160 KB e faz **zero requisições de rede**. As fontes estão
embutidas como data URI e todos os dados estão no próprio JavaScript. Isso
significa que ele funciona offline, aberto direto do disco, e pode ser enviado
por e-mail como anexo único.

---

## Estrutura

```
index.html              página pronta, é o que a Vercel publica
data/page.json          números da rodada do dia, gerado
src/
  template.html         fonte da página, com placeholders
  pagedata.py           coleta a rodada do dia e escreve o data/page.json
  build.py              injeta dados + fontes e gera o index.html
  fonts/                3 arquivos .woff2 + licenças (SIL OFL 1.1)
forecast_santa_maria.py análise meteorológica, relatório de terminal
snapshots/              histórico das execuções
.github/workflows/      a automação diária
```

### Alterando a página

Edite `src/template.html`, nunca o `index.html` (ele é gerado e será
sobrescrito). Depois:

```bash
python src/pagedata.py --target 2026-10-03   # busca os números do dia
python src/build.py                           # gera o index.html
```

---

## A atualização automática

A página **se refaz sozinha todo dia**, sem ninguém rodar nada. O workflow
`.github/workflows/atualiza.yml` roda às 09:00 UTC (06:00 em Santa Maria,
depois que as rodadas 00Z do ECMWF e do GFS publicam), regenera o
`index.html` e dá push. A Vercel republica no push, então o site fica novo
poucos minutos depois.

O commit só acontece se algum número mudou de verdade — `git diff --staged
--quiet` decide —, então não há commit à toa.

### O que é dinâmico e o que não é

Só entra no `data/page.json` o que realmente muda de um dia para o outro:

| Dinâmico, sai do `page.json` | Estático, fica no template |
|---|---|
| data da rodada e dias restantes | os 42%, 20% e 5% de chuva |
| os 50 cenários do SEAS5 | a grade dos 35 anos |
| a previsão determinística (a partir de 18/set) | as curvas horárias de temperatura e vento |
| o veredito | a seção do El Niño |
| a tabela de convergência | as recomendações práticas |

A climatologia é fixa de propósito: são 35 anos de medição já fechados, não
mudam nunca. Deixá-la no template evita requisição desnecessária e mantém a
página funcionando mesmo se o `page.json` faltar — nesse caso o build ainda
gera uma página válida, só sem os blocos do dia.

### A virada de 18 de setembro

Enquanto faltarem mais de 15 dias, `page.json` sai com `tier: "sazonal"` e a
seção **“O que os modelos estão vendo agora”** fica escondida, porque não há o
que mostrar. Em **18 de setembro** o dia 3 entra no alcance de 16 dias, o tier
vira `deterministico` e a seção aparece sozinha, com a tabela dos quatro
modelos e a dispersão entre eles.

### O veredito é escrito por regra, não à mão

`veredito()` em `src/pagedata.py` monta o texto a partir dos números, sem
julgamento humano:

- **fora do alcance** → sempre a mesma resposta, porque a física não muda:
  não existe previsão, e o número honesto é a climatologia.
- **dentro do alcance** → o tom vem da probabilidade de chuva dos conjuntos
  (`≤25%` tende a não chover · `≥60%` chuva provável · no meio, indefinido) e
  a confiança vem da dispersão entre os modelos determinísticos (`≤5 mm` de
  diferença = concordam). Rajada acima de 40 km/h acrescenta um aviso.

Se algum dia a redação precisar mudar, mude a função — não o HTML, que é
regenerado.

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
| 15 dias ou menos | 7 modelos determinísticos + blend, 3 conjuntos (119 membros), mais climatologia | 18/set a 3/out/2026 |

Cada execução grava `snapshots/2026-10-03_run_AAAA-MM-DD.json`. O `--compare`
imprime a tabela de convergência, que mostra se o sinal está se firmando:

```
run          lead  Tmax med  Tmin med  Rain med  P>=1mm
2026-08-01     63      21.3      12.6       0.7      46
2026-09-10     23      21.7      13.9       1.0      52
```

A climatologia do ERA5 fica em cache na primeira execução, então as seguintes
levam segundos.

### O que mudou no script em setembro de 2026

A prioridade da análise é **chuva**, depois temperatura, depois vento.

Três coisas entraram na análise:

- **Vento.** `wind_gusts_10m_max` agora é coletado em todos os tiers. Rajada acima
  de 40 km/h atrapalha véu, penteado e decoração leve, e nenhum aplicativo comum
  mostra isso. É o terceiro fator, atrás de chuva e temperatura.
- **GEM (CMC/Canadá)** entrou em `DET_MODELS`, e a **média combinada**
  (`best_match`) entrou separada, em `BLEND_MODEL`. O blend fica fora do cálculo
  de dispersão de propósito: ele é a média dos outros, contá-lo como opinião
  independente encolheria a dispersão artificialmente.
- **MET Norway (yr.no)** via `api.met.no`, na função `metno()`. Horizonte de ~9
  dias, então hoje devolve `None` para o dia 3 — o que é a resposta certa, não uma
  falha.

O cache do ERA5 virou `era5_v2_*.json` porque o v1 não tinha a coluna de vento.
Um checkout antigo rebaixa o arquivo em vez de ler um cache incompleto.

### Rotina sugerida

1. Rode o script e anote a linha.
2. Confira o boletim de El Niño do CPC, atualizado toda segunda quinta-feira.
3. A partir de **18 de setembro**, passe a olhar o bloco determinístico. Observe
   a **dispersão entre modelos**, não a média: quando ECMWF, GFS, ICON e GEM
   convergirem dentro de uns 2 °C e 5 mm, o sinal é real.
4. A partir de **24 de setembro** o yr.no passa a alcançar a data.
5. A partir de **29 de setembro** a previsão vira acionável. Cruze com os
   alertas do INMET e o radar da Defesa Civil do RS.

---

## O que os dados dizem hoje (10 de setembro de 2026)

**Antecedência de 23 dias.** A previsibilidade determinística da atmosfera acaba
por volta de 10 a 15 dias. Nenhuma fonte no mundo consegue dizer o tempo do dia 3
de outubro hoje. O que existe é uma distribuição de probabilidade.

Verificado nesta rodada: o alcance dos modelos determinísticos termina em
**2026-09-25**, oito dias antes do alvo.

### Climatologia observada, ERA5 1991 a 2025, 3/out ± 5 dias (n = 385)

| Variável | média | p10 | p25 | mediana | p75 | p90 | mín | máx |
|---|---|---|---|---|---|---|---|---|
| Tmax (°C) | 22,3 | 18,0 | 19,7 | 21,7 | 24,3 | 28,1 | 13,4 | 36,5 |
| Tmin (°C) | 12,8 | 8,2 | 10,2 | 12,7 | 15,4 | 17,3 | 2,7 | 23,1 |
| Chuva (mm/dia) | 6,4 | 0,0 | 0,0 | 0,2 | 6,8 | 20,9 | 0,0 | 126,4 |
| **Rajada (km/h)** | **36,5** | **24,5** | **29,2** | **35,6** | **42,8** | **50,8** | **14,8** | **68,4** |

```
P(chuva >=  1 mm) = 42%      P(Tmax >= 25 °C) = 23%
P(chuva >=  5 mm) = 27%      P(Tmin <= 10 °C) = 24%
P(chuva >= 10 mm) = 20%      P(rajada >= 40 km/h) = 34%
P(chuva >= 20 mm) = 10%      P(rajada >= 50 km/h) = 11%
```

**O vento tem ciclo diário forte** e trabalha a favor do horário escolhido. Média
horária das rajadas (ERA5 1996–2025, 3/out ± 5 d):

| Hora | 07h | 10h | **13h** | 15h | **17h30** | 19h | 22h |
|---|---|---|---|---|---|---|---|
| Rajada média (km/h) | 21,1 | 29,8 | **31,7** | 30,9 | **~26,9** | 22,4 | 23,7 |

Pico às 13h, queda de 15% até a cerimônia e de 29% até as 19h. Pôr do sol às
**18h37**, então luz dourada e vento cedendo coincidem.

### ECMWF SEAS5, 50 membros, rodada de 10/09/2026

| Variável | média | p25 | mediana | p75 | mín | máx |
|---|---|---|---|---|---|---|
| Tmax (°C) | 22,2 | 19,6 | 21,7 | 24,7 | 14,2 | 32,4 |
| Tmin (°C) | 13,2 | 10,8 | 13,9 | 16,2 | 5,3 | 25,0 |
| Chuva (mm) | 8,4 | 0,0 | 1,0 | 7,8 | 0,0 | 68,3 |

`P(chuva ≥1 mm) = 52%` · `P(≥5 mm) = 32%` · `P(≥10 mm) = 20%`

O SEAS5 continua estatisticamente indistinguível da climatologia (mediana de Tmax
21,7 contra 21,7; chuva 52% contra 42%). O modelo **não carrega sinal utilizável**
para esta data, que é o resultado esperado e correto a 23 dias.

### El Niño, o único sinal real disponível — e ficou mais forte

- **NOAA CPC, boletim de 13 de agosto de 2026: El Niño Advisory em vigor.**
- Anomalia de Niño-3.4 em julho: **+1,4 °C** (era +1,2 no boletim de julho).
- **Mais de 90% de chance de El Niño muito forte** na primavera/verão 2026-27,
  contra os 81% da análise anterior.
- **69% de chance de ser um evento histórico**, superando em força todos os El
  Niño registrados desde 1950, no trimestre outubro–dezembro.

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
   chega em **18 de setembro de 2026**, daqui a 8 dias.
2. **Melhor estimativa hoje é climatológica, ajustada pela tendência:** máxima
   perto de **23 °C** (faixa provável 19 a 26), mínima perto de **13 °C** (10 a
   16), probabilidade de chuva mensurável de cerca de **45%**.
3. **O sinal mensal é muito mais forte que o diário, e subiu.** Outubro de 2026
   tende a ser bem mais chuvoso que os 203 mm normais. Isso não diz nada
   confiável sobre o dia 3, mas eleva a chance de o plano B ser necessário em
   algum momento da semana.
4. **Cauda pesada.** Em outubros de El Niño forte a cauda de chuva intensa
   engorda. Os 5% climatológicos de `P(≥30 mm/dia)` são um piso, não uma
   estimativa central.
5. **O vento é risco real e subestimado.** Um terço dos dias 3 de outubro medidos
   teve rajada acima de 40 km/h. O horário da cerimônia ajuda, mas penteado, véu
   e decoração leve devem ser pensados para vento.

---

## Fontes

Quatro fontes produziram os números desta rodada:

| Fonte | O que veio dela | Endpoint |
|---|---|---|
| **ERA5** (Copernicus/ECMWF) | climatologia, grade dos 35 anos, curva horária de temperatura **e de vento**, totais de outubro | `archive-api.open-meteo.com` |
| **ECMWF SEAS5** | os 50 cenários e os 52% de chuva | `seasonal-api.open-meteo.com` |
| **NOAA CPC** | estado do El Niño, os +90%, os 69% e a anomalia de +1,4 °C | `cpc.ncep.noaa.gov` |
| **MetSul / Defesa Civil-RS** | leitura regional de contexto: primavera com chuva e temporais acima da média no RS | `metsul.com` · `defesacivil.rs.gov.br` |

Estas foram consultadas e **não tinham o que informar** sobre o dia 3, porque o
alvo está além do alcance delas. Passam a valer nas datas indicadas:

| Fonte | Para quê | Vale a partir de | Endereço |
|---|---|---|---|
| **ECMWF · GFS · ICON · GEM** | os quatro determinísticos, comparados entre si | 18/set | `api.open-meteo.com` |
| **MET Norway (yr.no)** | blend público, ótimo no curto prazo | 24/set | `api.met.no` |
| **INMET** | previsão oficial e alertas com valor legal; estação A803 | 1º/out | `previsao.inmet.gov.br/4316907` |
| **CPTEC/INPE** | modelos brasileiros, para comparar | 1º/out | `tempo.cptec.inpe.br` |

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
