# Metal Fatigue (2000) — Tradução PT-BR

> Tradução não-oficial para o Português do Brasil do clássico RTS Metal Fatigue (2000).

---

## 📋 Sobre o projeto

Este projeto, assim como sua documentação, foi feito inteiramente com o uso da plataforma **CLAUDE**, sendo apenas alguns poucos termos corrigidos manualmente.

O projeto traduz **1.257 strings** do jogo Metal Fatigue para o Português do Brasil, cobrindo os textos visíveis no jogo:

- Menus principal e de pausa
- Briefings e diários das campanhas (Rimtech, Mil-Agro e Neuropa)
- Objetivos de missão (GOALS e BACKGROUND)
- Alertas e mensagens do SUPERVISOR durante a partida
- Dicas de tutorial
- Tela de resultado de missão
- Configurações, sala multiplayer e skirmish
- Descrições dos mapas competitivos

**Versão do jogo testada:** Metal Fatigue (Steam)  
**Plataforma:** PC (Steam)

---

## ✅ O que foi traduzido

| Categoria | Strings | Descrição |
|---|---|---|
| MISSAO | ~900 | Briefings, Log Entry, GOALS, BACKGROUND, objetivos, dicas |
| LIVRE | 134 | Menus, mensagens de sistema, multiplayer |
| HIBRIDO | 128 | Menu principal + tela de seleção de campanha |
| LIMITE | 133 | Menu de pausa, configurações, sala online |

### Termos mantidos em inglês (intencionalmente)

Nomes próprios do universo do jogo foram preservados: `Diego`, `Stefan`, `Jonus`, `Akiri`, `Komrov`, `Leo Cob`, `Bishop Rau`, `Lord Ghem`, `Issadora`, `Rimtech`, `Mil-Agro`, `Neuropa`, `Hedoth`, `Combot`, `Metajoules`, `Super Zoom`, `Matter Converter`, `Skirmish`

---

## Como foi traduzido?

Para mais detalhes leia `COMO_FUNCIONA.md`.

Com ajuda da CLAUDE foi feita engenharia reversa completa do formato binário proprietário **RIFF/TBDF** usado pelo jogo para armazenar todos os textos nos arquivos `.tbd`.

Foram descobertas **5 estruturas distintas** de armazenamento de strings:
- `simple` — reconstrução total do DATA (strings.tbd, MissionInfo pequenos)
- `surgical` — patch via IMPT + heap (menumulti.tbd)
- `hybrid` — surgical + inplace combinados (Menu.tbd)
- `gobjects` — inplace via OFFS→int32→string com slots de tamanho fixo (gobjects.tbd, MissionInfo.tbd)
- `inplace` — substituição direta (ingamemenu.tbd)

A descoberta mais complexa foi o mecanismo do `gobjects.tbd` e `MissionInfo.tbd`: o engine localiza cada string lendo `OFFS[k] → ponteiro int32 no DATA → offset real da string`. Cada slot tem tamanho fixo e deve ser preenchido com espaços de padding até o null final.

A CLAUDE criou a ferramenta `mf_tbd_tool_v4.py` que automatiza extração, tradução e aplicação do patch.

---

## 🛠️ Como instalar

### Pré-requisitos

- Jogo instalado via Steam
- Python 3.8 ou superior

### Passo a passo

**1. Faça backup da pasta TBD**

```
xcopy "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD" "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD_backup" /E /I
```

**2. Baixe os arquivos da tradução**

Baixe `mf_tbd_tool_v4.py` e `traducao_mf.json` da seção [Releases](../../releases) deste repositório e coloque em uma pasta de trabalho, por exemplo `C:\MetalFatigue_PTBR\`.

**3. Gere os arquivos patchados**

```
python mf_tbd_tool_v4.py patch "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD" traducao_mf.json "C:\MetalFatigue_PTBR\TBD_ptbr"
```

**4. Aplique no jogo**

```
xcopy "C:\MetalFatigue_PTBR\TBD_ptbr" "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD" /E /Y
```

**5. Jogue!**

Abra o jogo normalmente pelo Steam. Os textos aparecerão em **Português do Brasil**.

> ⚠️ Ajuste o caminho `I:\SteamLibrary\...` conforme a localização da sua instalação do Steam.

---

## 🔄 Como desinstalar / restaurar

Para voltar ao inglês original, restaure o backup:

```
xcopy "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD_backup" "I:\SteamLibrary\steamapps\common\Metal Fatigue\TBD" /E /Y
```

---

## ⚠️ Avisos

- Esta é uma tradução **não-oficial** — não tem relação com a Zeppelin Games, Flagstone Interactive ou 3DO
- Testada na versão Steam de Metal Fatigue (2000)
- Alguns textos de UI muito curtos foram mantidos em inglês por limitação de espaço na interface
- Textos sem acentos em menus são limitação do engine — o jogo usa ASCII puro nessas posições

---

## 🐛 Reportar erros

Encontrou um erro de tradução, texto cortado ou algo que não faz sentido em PT-BR? Abra uma [Issue](../../issues) com:

- Print da tela com o erro
- Contexto (qual missão, menu, campanha)
- Sugestão de tradução correta (opcional)

---

## 🔧 Para desenvolvedores

Quer contribuir ou criar uma tradução para outro idioma? Veja `COMO_FUNCIONA.md` para a documentação técnica completa do formato RIFF/TBDF e do funcionamento da ferramenta.

---

## 📜 Licença

Este projeto está licenciado sob a **MIT License**.

Metal Fatigue © 2000 Zeppelin Games / Flagstone Interactive / 3DO.  
Este projeto é uma tradução não-oficial sem vínculo com os detentores da propriedade intelectual.
