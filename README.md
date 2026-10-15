# Exportador de Pier Forces ETABS → TQS (pasta ETB)

Lê pela API do ETABS os esforços da tabela **Pier Forces** nas combinações `ULS-NBR-#` e grava,
na pasta `ETB` ao lado do modelo, os arquivos que o TQS lê:

| Arquivo | Conteúdo |
|---|---|
| `P2.csv`, `P9.csv`, … | um CSV por Pier assinalado no modelo |
| `P8-1.csv` … `P8-7.csv` | faces do pilar poligonal P8 (Piers `P8A` … `P8G` no ETABS; a letra vira o número da face) |
| `P8.csv` | pilar poligonal **completo**: as faces são reatribuídas ao Pier `P8` numa cópia do modelo e os esforços são extraídos de novo |
| `P8.txt` | só para pilares poligonais: lances do TQS em que cada face existe e a faixa de cada face |

### Pilares poligonais e faces

No ETABS, cada face de um pilar poligonal é um Pier com o nome do pilar seguido de uma letra:
`P1A`, `P1B` e `P1C` são as faces 1, 2 e 3 do pilar `P1`.

- Cada face é gravada com o número no lugar da letra: `P1-1.csv`, `P1-2.csv`, `P1-3.csv`. O mesmo
  nome aparece na coluna Pier e no `P1.txt`.
- O pilar completo sai em `P1.csv`, com as faces reatribuídas ao Pier `P1` numa cópia do modelo.
- Também é aceito o nome já numerado no ETABS (`P1-1`, `P1-2`…), usado no modelo da Torre C.
- A regra só vale para nomes em que a letra vem logo depois de um número. Por isso `CHK` ou `PAR` não
  são faces.
- Um pilar com uma única face (só `P5A`) é tratado como pilar comum, com o nome como está.
- Duas faces com o mesmo número no mesmo pilar (`P1A` e `P1-1`) são erro.

Arquivos do projeto:

| Arquivo | Conteúdo |
|---|---|
| [exportar_pier_forces.py](exportar_pier_forces.py) | motor (API do ETABS, CSV/TXT), linha de comando e a ponte com a interface |
| `ui/` | interface: `index.html`, `app.css`, `app.js`, fontes Barlow (OFL) e ícone. `ui/dev/` tem a API simulada, usada só no desenvolvimento |
| `build_exe.bat` / `build_exe.py` | geram o `.exe` |
| `tools/make_icon.py` | gera o `ui/app.ico` |
| `tests/` | testes sem ETABS |

## Executável (outro computador, sem Python)

Copie só **`dist\ExportarPierForces.exe`**, com uns 16 MB. O outro computador precisa apenas do
ETABS instalado e licenciado e do WebView2 do Edge. O WebView2 já vem no Windows 11 e, em geral,
também no Windows 10 atualizado.

- Na primeira vez, o Windows pode mostrar "O Windows protegeu o computador", porque o executável
  não é assinado. Clique em **Mais informações → Executar assim mesmo**.
- Ao abrir, o canto inferior esquerdo mostra se a API do ETABS está acessível e quais ETABS estão
  instalados. Se aparecer erro de API, execute como administrador o `RegisterETABS.exe` da pasta
  do ETABS.
- Pelo Prompt de Comando, as mesmas opções da linha de comando funcionam, por exemplo
  `ExportarPierForces.exe --diagnostico` ou `ExportarPierForces.exe --modelo "C:\...\modelo.EDB"`.

**Gerar o .exe de novo** depois de mudar o código: suba o `__version__` no topo do `.py` e dê duplo
clique em `build_exe.bat`. Ele cria um ambiente separado em `build\venv`, sem mexer no Python da
máquina, e grava o executável em `dist\`. Na primeira vez precisa de internet para instalar o
PyInstaller e o pywebview. Se o `.exe` antigo estiver aberto, feche-o antes; se preferir, rode
`build\venv\Scripts\python.exe build_exe.py <outra pasta>`.
As classes da API do ETABS são geradas do ETABS instalado na máquina do build e vão embutidas no
`.exe`.

## Instalação para rodar o .py (desenvolvimento)

1. Python 3.10 ou mais novo, **64 bits**.
2. `pip install comtypes pywebview`. O `executar.bat` usa o `.venv` do projeto, se ele existir.
3. Se a API não for encontrada, execute como administrador o `RegisterETABS.exe` da pasta do ETABS.

## Uso

Abra `ExportarPierForces.exe` (ou `executar.bat`). A janela guia em 5 passos, e a barra lateral
mostra o que está completo e o que falta:

1. **Modelo**: escolha o `.EDB` (ou um dos modelos recentes) e clique em **Ler modelo no ETABS**.
   O modelo é aberto sem ser alterado, e aparecem os Piers, os pilares poligonais, as combinações e
   os Stories.
2. **Combinações**: as `ULS-NBR-#` já vêm marcadas. Há busca e botões para marcar a regra padrão,
   todas ou nenhuma.
3. **Pilares**: cada pilar poligonal aparece num cartão com o esquema da seção e as faces
   (`P8A → P8-1`…). O
   interruptor liga ou desliga a geração do pilar completo (`P8.csv` + `P8.txt`). Clique num Pier
   ou num cartão para excluí-lo.
4. **Lances TQS**: digite o lance do TQS de cada Story; Enter e as setas passam de linha.
   - **Preencher para cima**: a partir da linha selecionada, soma +1 a cada Story usado acima dela.
   - A coluna **Corte** desenha os pilares poligonais nos Stories em que eles existem. O pilar em
     destaque fica em azul, e em âmbar onde vale uma exceção.
   - **Exceções por pilar**: um Story do ETABS que corresponde a outro lance num pilar. Ex.: na
     Torre C, o `Story1` cobre os lances 1 a 5 e o P106 nasce no lance 2. Uma exceção do `P106` vale
     também para `P106-1`, `P106-2`…
   - Tudo é salvo em `story_map.csv`, ao lado do modelo. **Importar story_map…** carrega um arquivo
     pronto, como o `story_map_torre_C.csv`.
5. **Exportar**: o resumo mostra as pendências, e o progresso mostra cada etapa com tempo e contagem.
   No fim, aparecem a lista de arquivos gerados, os avisos e o botão **Abrir pasta ETB**.

As escolhas de cada modelo (combinações, Piers excluídos, pilares completos), os modelos recentes e o
tema (escuro ou claro, no canto da barra lateral) ficam salvos em
`%APPDATA%\ExportarPierForces\settings.json`. O log fica no botão **Log**, no rodapé (Ctrl+L).

### Linha de comando (sem janela)

```
python exportar_pier_forces.py --modelo "C:\...\modelo.EDB"
python exportar_pier_forces.py --modelo "C:\...\modelo.EDB" --comparar "C:\...\ETB de referência"
python exportar_pier_forces.py --modelo "C:\...\modelo.EDB" --listar
python exportar_pier_forces.py --modelo "C:\...\modelo.EDB" --sem-completo
```

## O que acontece na exportação

**Etapa 1 — modelo como está.** Para cada combinação `ULS-NBR-#`, uma chamada a
`Results.PierForce`, com as unidades temporariamente em tonf/m (restauradas no fim). O programa
nunca altera sinais nem valores.

**Etapa 2 — pilares poligonais completos** (só se houver pilares com 2 ou mais faces):

1. Copia o `.EDB` e os arquivos de resultado para `_pier_completo_tmp\`, ao lado do modelo. **O modelo
   original nunca é alterado nem salvo.**
2. Abre a cópia num ETABS iniciado pelo programa. Os ETABS que você já tinha aberto não são usados.
3. Troca o Pier de todo objeto (área ou barra) de `P8A`, `P8B`… para `P8` (`AreaObj/FrameObj.SetPier`).
4. O ETABS aceita trocar o Pier Label com o modelo analisado. Assim, a cópia continua travada com os
   resultados copiados e **não é reanalisada**. A reanálise (`RunAnalysis`) só acontece como plano
   B: se os arquivos de resultado não puderem ser copiados, se o ETABS recusar a troca ou se a cópia
   não devolver o pilar completo.
5. Extrai `P8`, confere que os Piers não reatribuídos têm esforços idênticos aos da etapa 1, fecha o
   ETABS e apaga a cópia.

**Gravação.** Os arquivos são gerados numa pasta temporária e só então substituem a pasta `ETB`. A pasta
`ETB` anterior é renomeada para `ETB_anterior_<data>`, porque o TQS lê tudo o que estiver dentro
dela.

Log completo: `exportar_pier_forces.log`, na pasta do modelo.

## Formato dos arquivos

**CSV** — igual ao exportado pelo Excel em português:

```
TABLE:  Pier Forces;;;;;;;;;;
Story;Pier;Output Case;Case Type;Location;P;V2;V3;T;M2;M3
;;;;;tonf;tonf;tonf;tonf-m;tonf-m;tonf-m
50;P2;ULS-NBR-1;Combination;Top;-22,06;25,22;4,93;1,22;-5,38;52,66
```

- `;`, vírgula decimal, 2 casas (arredondamento como o Excel), nunca `-0,00`; cp1252, CRLF.
- Story (lance do TQS) de cima para baixo → combinação → ordem da API. Nas combinações envelope
  (ULS-NBR-1 a 3), o par Top/Bottom Max vem antes do Min.

**TXT** — TAB, CRLF, sem quebra de linha no fim, lances de baixo para cima:

```
lance	1
P8-1	1
P8-2	2
lance	6
P8-1	1
...
```

A **faixa** (segundo número) é, por enquanto, o número da face (`P8-3` → 3), como em todos os
arquivos de referência da Torre C. A regra real do TQS ainda vai ser investigada: função
`face_faixa()`.

## Configuração

No topo de `exportar_pier_forces.py`: combinações (`COMBINATION_REGEX`), Piers
(`PIER_LIST`/`PIER_REGEX`/`PIER_EXCLUDE`), padrão de nome das faces (`FACE_LETTER_REGEX` e
`FACE_NUMBER_REGEX`; `None` desliga uma das convenções),
unidades, formato, `KEEP_WORK_COPY` (mantém a cópia de trabalho para conferência) e
`ETABS_PROGRAM_PATH`.

## Interface no navegador (desenvolvimento)

`ui/index.html?mock` carrega uma API simulada (`ui/dev/mock.js`) com os dados da Torre C
(`ui/dev/demo.json`). Com isso dá para trabalhar no visual sem ETABS e sem Python:

```
python -m http.server 8791 --directory ui
```

Depois, abra `http://localhost:8791/index.html?mock` no navegador. `?mock=fail` simula uma falha na
reatribuição. A pasta `ui/dev/` não vai para o `.exe`.

## Testes (sem ETABS)

```
python -m unittest discover -s tests -v
```

`tests/fake_etabs.py` simula a API: formato de retorno do comtypes, modelo travado, reatribuição e
reanálise. Com a planilha e a pasta `ETB` da Torre C na pasta do projeto, o teste de integração roda
as duas etapas com os valores da planilha e compara a pasta `ETB` gerada, byte a byte, com a de
referência. Para esse teste é preciso `pip install openpyxl`.

Resultado atual: 63 de 64 arquivos idênticos. O `P8-7.csv` de referência não tem a linha
`TABLE:  Pier Forces`, provavelmente por edição manual; fora isso, é idêntico.

## Pendências

- Rodar contra um ETABS real. A extração com `PierForce`, a reatribuição e a reanálise da cópia só
  foram testadas no ETABS simulado. Pontos a confirmar:
  - se a API se comporta como a interface, trocando o Pier Label sem destravar o modelo (o usuário
    confirmou esse comportamento na interface do ETABS);
  - a ordem Max/Min;
  - o tempo de execução.
- Regra da faixa no `.txt`.
- Origem dos lances do TQS: hoje vem do `story_map.csv`; ver se dá para ler do TQS.
- Testar o `.exe` em outro computador, principalmente com outra versão do ETABS.
