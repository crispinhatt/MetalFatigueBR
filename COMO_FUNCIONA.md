# Como funciona — Documentação Técnica

Este documento descreve o processo técnico de engenharia reversa do formato de arquivos do Metal Fatigue e o funcionamento da ferramenta de tradução.

---

## O formato RIFF/TBDF

O Metal Fatigue armazena todos os seus textos em arquivos `.tbd` dentro da pasta `TBD` do jogo. Esses arquivos usam uma variação proprietária do formato RIFF com identificador `TBDF` (em vez do `WAVE` dos arquivos de áudio).

**Estrutura básica:**
```
RIFF [tamanho] TBDF
  IMPT [tamanho] [dados — tabela de offsets com CRC32]
  DATA [tamanho] [strings null-terminated + dados binários]
  OFFS [tamanho] [ponteiros para ponteiros de strings]
  TYPE [tamanho] [tipos dos objetos]
```

---

## Os 5 modos de patch descobertos

### 1. LIVRE — `patch_simple`
**Arquivos:** `strings.tbd`, `misc.tbd`, `MultiInfo.tbd`, briefings pequenos  
**Mecanismo:** O IMPT aponta diretamente para as strings no DATA. O patch reconstrói o DATA inteiro com as strings traduzidas e atualiza todos os offsets no IMPT e no OFFS.

### 2. LIVRE — `patch_surgical`
**Arquivos:** `menumulti.tbd`  
**Mecanismo:** O DATA contém dados binários além das strings. O patch substitui as strings in-place (se couberem no slot original) ou as move para um heap anexado ao final do DATA, atualizando os offsets no IMPT.

### 3. HIBRIDO — `patch_hybrid`
**Arquivos:** `Menu.tbd`  
**Mecanismo:** Tem dois tipos de strings:
- Via IMPT (briefings, descrições de corporação) → patch_surgical
- Embutidas diretamente no DATA sem IMPT (botões do menu) → patch_inplace

### 4. MISSAO — `patch_gobjects`
**Arquivos:** `gobjects.tbd` e `MissionInfo.tbd` de cada pasta de missão  
**Mecanismo mais complexo — descoberto por comparação com a tradução russa:**

```
OFFS[k] → offset no DATA → int32 (ponteiro) → offset real da string
```

Cada string ocupa um **slot de tamanho fixo**. A string é escrita no slot e o espaço restante é preenchido com espaços (`0x20`), seguido de null (`0x00`). Os offsets NUNCA mudam — por isso o OFFS e os int32 não precisam ser atualizados.

> **Descoberta crítica:** O `MissionInfo.tbd` das pastas de missão tem ~2MB de dados de mapa 3D, mas os primeiros ~3KB contêm as strings de texto usando o mesmo mecanismo OFFS. O engine lê o briefing do `MissionInfo.tbd`, não do `gobjects.tbd` — ambos têm os mesmos textos mas é o MissionInfo que é exibido na tela.

### 5. LIMITE — `patch_inplace`
**Arquivos:** `ingamemenu.tbd`  
**Mecanismo:** Strings embutidas em blocos de UI binários. Substituição direta respeitando o slot disponível.

---

## A ferramenta: `mf_tbd_tool_v4.py`

### Comandos

```bash
# Extrai todas as strings traduzíveis para JSON
python mf_tbd_tool_v4.py extract "caminho\para\TBD"

# Aplica as traduções do JSON nos arquivos TBD
python mf_tbd_tool_v4.py patch "caminho\para\TBD" traducao_mf.json "caminho\saida"

# Verifica quais strings foram aplicadas
python mf_tbd_tool_v4.py verify "caminho\para\TBD" "caminho\saida"
```

### Estrutura do JSON

```json
{
  "_info": { ... },
  "arquivos": {
    "X_01\\gobjects.tbd": [
      {
        "mode": "gobjects",
        "offset": 7824,
        "max_length": 831,
        "original": "The first nexus subject is Diego Angelus...",
        "translated": "O primeiro sujeito nexus e Diego Angelus..."
      }
    ]
  }
}
```

- `max_length = -1` → tamanho livre, acentos permitidos
- `max_length = N` → máximo N bytes (ASCII apenas para LIMITE/MISSAO)

---

## Estrutura das pastas TBD

```
TBD/
├── strings.tbd          ← Mensagens de sistema, alertas
├── misc.tbd             ← Menus save/load
├── ingamemenu.tbd       ← Menu pause
├── Menu.tbd             ← Menu principal + seleção campanha
├── menumulti.tbd        ← Sala multiplayer
├── sound.tbd            ← Áudio (127 WAVs, não traduzido)
├── X_01/ ... X_10/      ← Campanha Rimtech (Diego)
│   ├── MissionInfo.tbd  ← Briefing + Log Entry + objetivos
│   └── gobjects.tbd     ← Mesmas strings (backup interno)
├── Y_01/ ... Y_10/      ← Campanha Mil-Agro (Stefan)
├── Z_01/ ... Z_10/      ← Campanha Neuropa (Jonus)
└── M2_01/ ... M8_30/    ← Mapas Skirmish/Multiplayer
```

---

## Versão futura (2.0)

- Clonagem e tradução das vozes do SUPERVISOR usando [jamiepine/voicebox](https://github.com/jamiepine/voicebox)
- O `sound.tbd` contém 127 WAVs mono 11025Hz 16-bit PCM prontos para processamento
