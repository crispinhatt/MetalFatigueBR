#!/usr/bin/env python3
"""
Metal Fatigue TBD Translation Tool v4
======================================
Extrai strings de TODA a pasta TBD em um único JSON e aplica as traduções.

ESTRUTURA DO JOGO (descoberta por engenharia reversa):
  Pasta TBD/raiz:
    strings.tbd      → mensagens de sistema, alertas, multiplayer  [LIVRE]
    misc.tbd         → menus de save/load                           [LIVRE]
    ingamemenu.tbd   → menu pause in-game                          [LIMITE]
    Menu.tbd         → menu principal + seleção de campanha        [HIBRIDO]
    menumulti.tbd    → configurações de sala multiplayer           [LIVRE]

  Pastas X_NN/ (campanha Rimtech):
    MissionInfo.tbd  → briefing da missão (~2KB)                   [LIVRE]
    MultiInfo.tbd    → briefing modo multiplayer                    [LIVRE]
    gobjects.tbd     → Log Entry + GOALS + objetivos + dicas       [MISSAO]

  Pastas Y_NN/ (campanha Mil-Agro) e Z_NN/ (Neuropa): mesmo padrão
  Pastas M_NN/ (skirmish/multiplayer): gobjects.tbd tem objetivos  [MISSAO]

MODOS DE PATCH:
  LIVRE   → Reconstrução total. Strings de qualquer tamanho, acentos livres.
  HIBRIDO → Menu.tbd: surgical (IMPT livre) + inplace (strings embutidas).
  MISSAO  → gobjects.tbd: Log Entry, GOALS, BACKGROUND, objetivos, dicas.
             Inplace com slots generosos (até 900 bytes disponíveis).
  LIMITE  → ingamemenu.tbd: inplace restrito, respeitar max_length.

COMANDOS:
  python mf_tbd_tool_v4.py extract <pasta_TBD>
      Varre toda a pasta TBD e gera traducao_mf.json

  python mf_tbd_tool_v4.py patch <pasta_TBD> traducao_mf.json <pasta_saida>
      Aplica as traduções e gera os arquivos modificados

  python mf_tbd_tool_v4.py verify <pasta_TBD> <pasta_saida>
      Verifica quais strings foram aplicadas

WORKFLOW:
  1. python mf_tbd_tool_v4.py extract "I:\\...\\Metal Fatigue\\TBD"
  2. Edite traducao_mf.json — preencha "translated" para cada string
     max_length = -1  → livre (LIVRE, HIBRIDO impt, MISSAO)
     max_length =  N  → máximo N bytes (LIMITE, HIBRIDO data)
  3. python mf_tbd_tool_v4.py patch "I:\\...\\TBD" traducao_mf.json "J:\\...\\TBD_ptbr"
  4. Backup + xcopy
"""

import sys, json, re, struct, shutil
from pathlib import Path


# ================================================================
# ARQUIVOS A IGNORAR COMPLETAMENTE
# ================================================================
SKIP_FILES = {
    # Geometria 3D, paletas, animações, fontes
    '3dstructuresx.tbd', '3dstructuresy.tbd', '3dstructuresz.tbd',
    '3dvehicles.tbd', 'animbase.tbd', 'animoverlay.tbd',
    'bgpalette.tbd', 'bgpalettebw.tbd', 'explosion.tbd',
    'font.tbd', 'gobjectpalettes.tbd', 'indicators.tbd',
    'intropalettes.tbd', 'ingameradial.tbd', 'logo.tbd',
    'logofrench.tbd', 'logogerman.tbd', 'logoitalian.tbd',
    'logospanish.tbd', 'master.tbd', 'hotkeys.tbd',
    # Terreno, estruturas, veículos
    'background.tbd', 'defends.tbd',
    'structuresx.tbd', 'structuresy.tbd', 'structuresz.tbd',
    'vehiclesx.tbd',  'vehiclesy.tbd',  'vehiclesz.tbd',
    'toolbarx.tbd',   'toolbary.tbd',   'toolbarz.tbd',
    'sound.tbd',
    # Peças de robô — nomes técnicos em inglês (decisão de projeto)
    'objinfo.tbd',
    'robotpartsaxe.tbd',         'robotpartsgattlinggun.tbd',
    'robotpartshowitzer.tbd',    'robotpartspowershield.tbd',
    'robotpartsrotaryblade.tbd', 'robotpartshammerhand.tbd',
    'robotpartsmissilearm.tbd',  'robotpartslasersword.tbd',
    'robotpartsneutronbomb.tbd', 'robotpartskatana.tbd',
    'robotpartsbladefist.tbd',   'robotpartselectrograsp.tbd',
    'robotpartsphasechanger.tbd','robotpartsmulticlaw.tbd',
    'robotpartsjetpack.tbd',     'robotpartscarpetbomb.tbd',
    'robotpartsorbitalbomb.tbd', 'robotpartsblastpulse.tbd',
    'robotpartsprotoblast.tbd',  'robotpartssniperbeam.tbd',
    'robotpartsenergygun.tbd',   'robotpartspowergun.tbd',
    'robotpartslasergun.tbd',    'robotpartsplasmagun.tbd',
    'robotpartspwrpulse.tbd',    'robotpartshoming.tbd',
    'robotpartsforcefield.tbd',  'robotpartsareacloak.tbd',
    'robotpartsselfrepair.tbd',  'robotpartsspeed.tbd',
    'robotpartsstrength.tbd',    'robotpartshthupgrade.tbd',
    'robotpartssteady.tbd',      'robotpartsjointbooster.tbd',
    'robotpartsjetsboots.tbd',
    # Árvore tecnológica
    'techtree.tbd', 'prebuildtechtree.tbd',
}

# Menu principal: mode híbrido (IMPT livre + DATA embutido limitado)
HYBRID_FILES  = {'menu.tbd'}

# Menu pause: inplace puro (strings embutidas em blocos de UI binário)
INPLACE_FILES = {'ingamemenu.tbd'}

# gobjects.tbd: Log Entry, GOALS, BACKGROUND, objetivos, dicas de tutorial
GOBJECTS_FILE = 'gobjects.tbd'

# DATA maior que este limite + nome missioninfo = arquivo de mapa, não briefing
UI_DATA_THRESHOLD = 50_000


# ================================================================
# RIFF/TBDF
# ================================================================

def parse_riff(data: bytes):
    if len(data) < 12 or data[0:4] != b'RIFF' or data[8:12] != b'TBDF':
        raise ValueError("Nao e RIFF/TBDF valido")
    chunks, order = {}, []
    pos = 12
    while pos + 8 <= len(data):
        cid  = data[pos:pos+4].decode('ascii', errors='replace')
        csz  = int.from_bytes(data[pos+4:pos+8], 'little')
        chunks[cid] = {'offset': pos, 'size': csz, 'data': data[pos+8:pos+8+csz]}
        order.append(cid)
        pos += 8 + csz + (csz % 2)
    return chunks, order


def make_chunk(cid: str, data: bytes) -> bytes:
    out = cid.encode('ascii') + struct.pack('<I', len(data)) + bytes(data)
    if len(data) % 2:
        out += b'\x00'
    return out


def read_cstring(data: bytes, off: int) -> bytes:
    j = off
    while j < len(data) and data[j] != 0x00:
        j += 1
    return data[off:j]


def encode_str(text: str) -> bytes:
    try:
        return text.encode('latin-1')
    except Exception:
        return text.encode('ascii', errors='replace')


# ================================================================
# DETECÇÃO DE TEXTO TRADUZÍVEL
# ================================================================

def is_text(raw: bytes) -> bool:
    """
    True se raw é uma string de texto ASCII traduzível.
    Múltiplas heurísticas para eliminar dados binários disfarçados de texto.
    """
    if len(raw) < 4:
        return False
    # Deve ser 100% ASCII imprimível + \t \n \r
    for b in raw:
        if b < 0x20 and b not in (0x09, 0x0A, 0x0D):
            return False
        if b > 0x7E:
            return False
    try:
        txt = raw.decode('ascii')
    except Exception:
        return False

    # Não pode começar com \n, \r ou \t
    # EXCETO: \r\n seguido de letra ou * = parágrafo formatado (gobjects.tbd)
    if txt[0] in '\n\r\t':
        if txt[:2] == '\r\n' and len(txt) > 2 and (txt[2].isalpha() or txt[2] == '*'):
            pass  # parágrafo formatado válido
        else:
            return False

    # Pelo menos 2 letras consecutivas
    if not re.search(r'[A-Za-z]{2,}', txt):
        return False
    # Identificadores internos curtos
    if re.match(r'^[A-Z_]{1,6}$', txt):
        return False
    # 3+ chars idênticos consecutivos (exceto '.') = dado de geometria
    for i in range(len(txt) - 2):
        c = txt[i]
        if c != '.' and c == txt[i+1] == txt[i+2]:
            return False
    # Caminhos, extensões, cabeçalho RIFF
    if '\\' in txt or ')(' in txt:
        return False
    if re.search(r'\.(tbd|avi|bmp|wav|mp3|dll|exe)$', txt, re.I):
        return False
    if txt.startswith('RIFF'):
        return False
    # Chars absolutamente proibidos (# removido — aparece em 'Serial #', 'disc #1')
    if any(c in '`^{}[|@~]><$' for c in txt):
        return False
    # Padrão X:Y:Z repetido = dados de mapa
    if txt.count(':') >= 3:
        return False
    # Filtros para strings sem espaço/newline
    if not any(c in txt for c in ' \n\r\t'):
        # Padrão quase-alternado período 2 (AnAnAm, IJIJIJ)
        pat, segs = txt[:2], len(txt) // 2
        if segs >= 3:
            matches = sum(1 for i in range(segs) if txt[i*2:(i+1)*2] == pat)
            if matches / segs >= 0.66:
                return False
        # CamelCase composto longo (RobotPartsAxe)
        if len(txt) > 10:
            inner_upper = sum(1 for i, c in enumerate(txt) if c.isupper() and i > 0)
            if inner_upper >= 2:
                return False
        # Mais de 25% de dígitos
        if sum(1 for c in txt if c.isdigit()) / len(txt) > 0.25:
            return False
        # Análise das letras
        letters = [c for c in txt.lower() if c.isalpha()]
        if letters:
            vowels = sum(1 for c in letters if c in 'aeiou')
            if vowels / len(letters) < 0.10:
                return False
            if sum(1 for c in letters if c in 'qwxzkj') / len(letters) > 0.30:
                return False
            run = 0
            for c in txt.lower():
                if c.isalpha():
                    run = 0 if c in 'aeiou' else run + 1
                    if run >= 5:
                        return False
                else:
                    run = 0
    # Strings curtas suspeitas
    stripped = txt.strip()
    if len(stripped) <= 5:
        if re.match(r'^[A-Z]{2,5}$', stripped):
            return False
        if not re.match(r'^[A-Za-z][a-z]{2,}$', stripped):
            if re.search(r'[^A-Za-z\s]', stripped):
                return False
    return True


def impt_has_text(chunks: dict) -> bool:
    """True se IMPT aponta para pelo menos 1 string ASCII traduzível."""
    impt = chunks.get('IMPT', {}).get('data', b'')
    dc   = chunks.get('DATA', {}).get('data', b'')
    if not impt or not dc:
        return False
    seen = set()
    for i in range(0, len(impt) - 7, 8):
        off = int.from_bytes(impt[i:i+4], 'little')
        if off >= len(dc) or off in seen:
            continue
        seen.add(off)
        if is_text(read_cstring(dc, off)):
            return True
    return False


# ================================================================
# CLASSIFICAÇÃO
# ================================================================

def classify(filepath: Path, chunks: dict) -> str:
    """
    Retorna o modo de patch:
      'simple'   — reconstrução total, strings livres
      'surgical' — IMPT + heap, strings livres
      'hybrid'   — surgical + inplace (Menu.tbd)
      'gobjects' — inplace especial (gobjects.tbd)
      'inplace'  — substituição direta, respeita max_length
    """
    name    = filepath.name.lower()
    dc_size = chunks.get('DATA', {}).get('size', 0)

    if name == GOBJECTS_FILE:
        return 'gobjects'
    if name in INPLACE_FILES:
        return 'inplace'
    if name in HYBRID_FILES:
        return 'hybrid'
    # MissionInfo.tbd grande = arquivo de mapa com texto nos primeiros slots
    # Usa o mesmo mecanismo do gobjects.tbd (OFFS → ptr → string)
    if name == 'missioninfo.tbd' and dc_size > UI_DATA_THRESHOLD:
        return 'gobjects'

    if impt_has_text(chunks):
        return 'surgical' if dc_size >= UI_DATA_THRESHOLD else 'simple'
    if dc_size >= UI_DATA_THRESHOLD:
        return 'inplace'
    return 'simple'


# ================================================================
# EXTRAÇÃO
# ================================================================

def extract_via_impt(chunks: dict, mode: str) -> list:
    """Extrai strings via IMPT. Strings com tamanho livre (max_length=-1)."""
    impt = chunks.get('IMPT', {}).get('data', b'')
    dc   = chunks.get('DATA', {}).get('data', b'')
    if not impt or not dc:
        return []

    results, seen = [], set()
    for i in range(0, len(impt) - 7, 8):
        off   = int.from_bytes(impt[i:i+4], 'little')
        crc32 = int.from_bytes(impt[i+4:i+8], 'little')
        if off >= len(dc) or off in seen:
            continue
        seen.add(off)
        raw = read_cstring(dc, off)
        if not is_text(raw):
            continue
        results.append({
            'mode':       mode,
            'impt_index': i // 8,
            'offset':     off,
            'crc32':      f'0x{crc32:08X}',
            'max_length': -1,
            'original':   raw.decode('latin-1'),
            'translated': raw.decode('latin-1'),
        })

    # Remove sufixos duplicados (2 ponteiros IMPT para a mesma string)
    originals = [s['original'] for s in results]
    results = [
        s for s in results
        if not any(big != s['original'] and big.endswith(s['original'])
                   for big in originals)
    ]
    # Remove duplicatas de texto idêntico — mantém primeira ocorrência
    seen_text, deduped = set(), []
    for s in sorted(results, key=lambda x: x['offset']):
        if s['original'] not in seen_text:
            seen_text.add(s['original'])
            deduped.append(s)
    return deduped


def extract_inplace_raw(chunks: dict, mode: str) -> list:
    """Extrai strings por varredura heurística do DATA. Respeita slot."""
    dc = chunks.get('DATA', {}).get('data', b'')
    if not dc:
        return []

    results, i = [], 0
    while i < len(dc):
        j = i
        while j < len(dc) and dc[j] != 0x00:
            j += 1
        raw = dc[i:j]
        if is_text(raw):
            k = j
            while k < len(dc) and dc[k] == 0x00:
                k += 1
            results.append({
                'mode':       mode,
                'offset':     i,
                'max_length': k - i - 1,
                'original':   raw.decode('latin-1'),
                'translated': raw.decode('latin-1'),
            })
        i = j + 1
    return results


def extract_hybrid(chunks: dict) -> list:
    """
    Menu.tbd: combina IMPT (livre) + DATA embutido (limitado).
    Deduplicação: string que está no IMPT não aparece no DATA.
    """
    impt_strs    = extract_via_impt(chunks, 'hybrid_impt')
    data_strs    = extract_inplace_raw(chunks, 'hybrid_data')
    impt_texts   = {s['original'] for s in impt_strs}
    data_filtered = [s for s in data_strs if s['original'] not in impt_texts]
    return impt_strs + data_filtered


def extract_gobjects(chunks: dict) -> list:
    """
    gobjects.tbd / MissionInfo.tbd: extrai strings via OFFS → int32 → string.
    O engine localiza cada string lendo OFFS[k] → ptr no DATA → offset da string.
    Os slots têm tamanho FIXO: string + espaços de padding + null.
    max_length = slot_size - 1 (espaço real disponível para texto).
    Ignora slots com dados binários (bytes > 0x7E).
    """
    dc   = chunks.get('DATA', {}).get('data', b'')
    offs = chunks.get('OFFS', {}).get('data', b'')
    if not dc or not offs:
        return []

    count = int.from_bytes(offs[0:4], 'little')

    # Mapeia: str_offset → ptr_offset (onde no DATA está o int32 ponteiro)
    ptr_map = {}
    for k in range(1, count + 1):
        po  = int.from_bytes(offs[k*4:(k+1)*4], 'little')
        if po + 4 > len(dc):
            continue
        ptr = int.from_bytes(dc[po:po+4], 'little')
        if ptr < len(dc):
            ptr_map[ptr] = po

    if not ptr_map:
        return []

    str_offsets = sorted(ptr_map.keys())

    results = []
    for i, off in enumerate(str_offsets):
        raw = read_cstring(dc, off)

        # Slot size = distância até o próximo str_offset
        next_off  = str_offsets[i+1] if i+1 < len(str_offsets) else off + len(raw) + 1
        slot_size = next_off - off    # string + padding + null
        max_len   = slot_size - 1     # máximo de bytes de texto (sem o null)

        # Ignora slots com dados binários (bytes fora do range ASCII)
        if any(b > 0x7E for b in raw):
            continue

        # Ignora slots muito grandes (dados de mapa embutidos)
        if slot_size > 50_000:
            continue

        # Ignora strings muito curtas sem conteúdo traduzível
        try:
            txt = raw.decode('ascii')
        except Exception:
            continue

        if len(txt.strip()) < 3:
            continue

        results.append({
            'mode':       'gobjects',
            'offset':     off,
            'ptr_offset': ptr_map[off],
            'max_length': max_len,
            'original':   txt,
            'translated': txt,
        })

    return results


# ================================================================
# PATCH — SIMPLE
# ================================================================

def patch_simple(orig: bytes, tmap: dict) -> bytes:
    """Reconstrói o DATA inteiro. Strings de qualquer tamanho."""
    chunks, order = parse_riff(orig)
    if 'DATA' not in chunks or 'IMPT' not in chunks:
        return orig

    impt_ba = bytearray(chunks['IMPT']['data'])
    dc      = chunks['DATA']['data']
    offs_ba = bytearray(chunks['OFFS']['data']) if 'OFFS' in chunks else None

    ptr_offs = set()
    if offs_ba:
        cnt = int.from_bytes(offs_ba[0:4], 'little')
        for k in range(1, cnt + 1):
            po = int.from_bytes(offs_ba[k*4:(k+1)*4], 'little')
            if po < len(dc):
                ptr_offs.add(po)

    unique_offs = sorted(set(
        int.from_bytes(impt_ba[i:i+4], 'little')
        for i in range(0, len(impt_ba) - 7, 8)
        if int.from_bytes(impt_ba[i:i+4], 'little') < len(dc)
    ))
    last_end = max(
        (off + len(read_cstring(dc, off)) + 1 for off in unique_offs),
        default=0
    )
    tail = dc[last_end:]

    old_to_new, new_dc, cur = {}, bytearray(), 0
    for old_off in unique_offs:
        raw = read_cstring(dc, old_off)
        old_to_new[old_off] = cur
        if old_off in ptr_offs:
            new_dc += raw + b'\x00'
            cur += len(raw) + 1
        elif is_text(raw):
            nb = encode_str(tmap.get(raw.decode('latin-1'), raw.decode('latin-1')))
            new_dc += nb + b'\x00'
            cur += len(nb) + 1
        else:
            new_dc += raw + b'\x00'
            cur += len(raw) + 1

    for old_off in ptr_offs:
        if old_off not in old_to_new:
            continue
        raw = read_cstring(dc, old_off)
        if len(raw) >= 4:
            pointed_old = int.from_bytes(raw[0:4], 'little')
            if pointed_old in old_to_new:
                new_pos = old_to_new[old_off]
                new_dc[new_pos:new_pos+4] = struct.pack('<I', old_to_new[pointed_old])

    new_dc += tail

    new_impt = bytearray(impt_ba)
    for i in range(0, len(new_impt) - 7, 8):
        old_off = int.from_bytes(new_impt[i:i+4], 'little')
        if old_off in old_to_new:
            new_impt[i:i+4] = struct.pack('<I', old_to_new[old_off])

    new_offs = None
    if offs_ba:
        new_offs = bytearray(offs_ba)
        cnt = int.from_bytes(new_offs[0:4], 'little')
        for k in range(1, cnt + 1):
            po = int.from_bytes(new_offs[k*4:(k+1)*4], 'little')
            if po in old_to_new:
                new_offs[k*4:(k+1)*4] = struct.pack('<I', old_to_new[po])

    result = bytearray(b'RIFF\x00\x00\x00\x00TBDF')
    for cid in order:
        if cid == 'IMPT':
            result += make_chunk('IMPT', bytes(new_impt))
        elif cid == 'DATA':
            result += make_chunk('DATA', bytes(new_dc))
        elif cid == 'OFFS' and new_offs is not None:
            result += make_chunk('OFFS', bytes(new_offs))
        else:
            result += make_chunk(cid, chunks[cid]['data'])
    result[4:8] = struct.pack('<I', len(result) - 8)
    return bytes(result)


# ================================================================
# PATCH — SURGICAL
# ================================================================

def patch_surgical(orig: bytes, tmap: dict) -> bytes:
    """DATA binário preservado. Strings menores = in-place. Maiores = heap."""
    chunks, order = parse_riff(orig)
    if 'DATA' not in chunks or 'IMPT' not in chunks:
        return orig

    impt_ba   = bytearray(chunks['IMPT']['data'])
    dc_ba     = bytearray(chunks['DATA']['data'])
    heap      = bytearray()
    heap_base = len(dc_ba)

    seen = set()
    for i in range(0, len(impt_ba) - 7, 8):
        off = int.from_bytes(impt_ba[i:i+4], 'little')
        if off in seen or off >= len(dc_ba):
            continue
        seen.add(off)
        raw = read_cstring(bytes(dc_ba), off)
        if not is_text(raw):
            continue
        try:
            orig_txt = raw.decode('ascii')
        except Exception:
            continue
        trans = tmap.get(orig_txt, orig_txt)
        if trans == orig_txt:
            continue
        nb = encode_str(trans)
        j = off + len(raw)
        k = j
        while k < len(dc_ba) and dc_ba[k] == 0x00:
            k += 1
        slot = k - off
        if len(nb) <= slot - 1:
            dc_ba[off:off+slot] = nb + b'\x00' * (slot - len(nb))
        else:
            dc_ba[off:off+slot] = b'\x00' * slot
            new_off = heap_base + len(heap)
            heap   += nb + b'\x00'
            impt_ba[i:i+4] = struct.pack('<I', new_off)

    result = bytearray(b'RIFF\x00\x00\x00\x00TBDF')
    for cid in order:
        if cid == 'IMPT':
            result += make_chunk('IMPT', bytes(impt_ba))
        elif cid == 'DATA':
            result += make_chunk('DATA', bytes(dc_ba) + bytes(heap))
        else:
            result += make_chunk(cid, chunks[cid]['data'])
    result[4:8] = struct.pack('<I', len(result) - 8)
    return bytes(result)


# ================================================================
# PATCH — INPLACE
# ================================================================

def patch_inplace(orig: bytes, tmap: dict) -> bytes:
    """Substitui strings no lugar respeitando o slot disponível."""
    chunks, order = parse_riff(orig)
    if 'DATA' not in chunks:
        return orig

    dc = bytearray(chunks['DATA']['data'])
    i  = 0
    while i < len(dc):
        j = i
        while j < len(dc) and dc[j] != 0x00:
            j += 1
        raw = dc[i:j]
        if is_text(raw):
            try:
                orig_txt = raw.decode('latin-1')
            except Exception:
                orig_txt = raw.decode('ascii', errors='replace')
            trans = tmap.get(orig_txt, orig_txt)
            if trans != orig_txt:
                k = j
                while k < len(dc) and dc[k] == 0x00:
                    k += 1
                max_len = (k - i) - 1
                nb = encode_str(trans)
                if len(nb) > max_len:
                    nb = nb[:max_len]
                slot    = max_len + 1
                dc[i:i+slot] = nb + b'\x00' * (slot - len(nb))
        i = j + 1

    result = bytearray(b'RIFF\x00\x00\x00\x00TBDF')
    for cid in order:
        if cid == 'DATA':
            result += make_chunk('DATA', bytes(dc))
        else:
            result += make_chunk(cid, chunks[cid]['data'])
    result[4:8] = struct.pack('<I', len(result) - 8)
    return bytes(result)


# ================================================================
# PATCH — GOBJECTS (inplace via OFFS com padding de espaços)
# ================================================================

def patch_gobjects(orig: bytes, tmap: dict) -> bytes:
    """
    gobjects.tbd: patch inplace usando OFFS → int32 → string.
    Cada slot tem tamanho FIXO. A tradução é escrita no slot e
    preenchida com ESPAÇOS até slot_size-1, seguido de null.
    Offsets não mudam → OFFS e int32 permanecem intactos.
    """
    try:
        chunks, order = parse_riff(orig)
    except Exception:
        return orig

    if 'DATA' not in chunks or 'OFFS' not in chunks:
        return orig

    dc_ba   = bytearray(chunks['DATA']['data'])
    offs_ba = chunks['OFFS']['data']

    # Mapeia str_offset → slot_size via OFFS
    count = int.from_bytes(offs_ba[0:4], 'little')
    ptr_map = {}  # str_offset → ptr_offset_no_DATA
    for k in range(1, count + 1):
        po  = int.from_bytes(offs_ba[k*4:(k+1)*4], 'little')
        if po + 4 > len(dc_ba):
            continue
        ptr = int.from_bytes(dc_ba[po:po+4], 'little')
        if ptr < len(dc_ba):
            ptr_map[ptr] = po

    if not ptr_map:
        return orig

    str_offsets = sorted(ptr_map.keys())

    for i, off in enumerate(str_offsets):
        raw      = read_cstring(bytes(dc_ba), off)
        next_off = str_offsets[i+1] if i+1 < len(str_offsets) else off + len(raw) + 1
        slot_size = next_off - off   # tamanho fixo do slot
        max_len   = slot_size - 1   # máximo de bytes de texto

        try:
            orig_txt = raw.decode('latin-1')
        except Exception:
            orig_txt = raw.decode('ascii', errors='replace')

        trans = tmap.get(orig_txt, orig_txt)
        if trans == orig_txt:
            continue

        nb = encode_str(trans)
        if len(nb) > max_len:
            nb = nb[:max_len]

        # Escreve: texto + espaços de padding + null obrigatório
        payload = nb + b' ' * (max_len - len(nb)) + b'\x00'
        dc_ba[off:off + slot_size] = payload

    result = bytearray(b'RIFF\x00\x00\x00\x00TBDF')
    for cid in order:
        if cid == 'DATA':
            result += make_chunk('DATA', bytes(dc_ba))
        else:
            result += make_chunk(cid, chunks[cid]['data'])
    result[4:8] = struct.pack('<I', len(result) - 8)
    return bytes(result)


# ================================================================
# PATCH — HYBRID (Menu.tbd)
# ================================================================

def patch_hybrid(orig: bytes, tmap: dict) -> bytes:
    """Menu.tbd: inplace primeiro (DATA embutido), depois surgical (IMPT)."""
    return patch_surgical(patch_inplace(orig, tmap), tmap)


# ================================================================
# COMANDO: EXTRACT
# ================================================================

MODO_LABEL = {
    'simple':      'LIVRE  ',
    'surgical':    'LIVRE  ',
    'hybrid':      'HIBRID.',
    'hybrid_impt': 'LIVRE  ',
    'hybrid_data': 'LIMITE ',
    'gobjects':    'MISSAO ',
    'inplace':     'LIMITE ',
}

MODO_LABEL_FILE = {
    'simple':   'LIVRE  ',
    'surgical': 'LIVRE  ',
    'hybrid':   'HIBRID.',
    'gobjects': 'MISSAO ',
    'inplace':  'LIMITE ',
}


def cmd_extract(tbd_folder: str):
    folder = Path(tbd_folder)
    if not folder.exists():
        print(f"Pasta nao encontrada: {folder}")
        sys.exit(1)

    tbd_files = sorted(folder.rglob('*.tbd'))
    print(f"Encontrados {len(tbd_files)} arquivos .tbd\nExtraindo...\n")

    all_files, total_strs, skipped = {}, 0, 0

    for tbd_path in tbd_files:
        rel = str(tbd_path.relative_to(folder))

        if tbd_path.name.lower() in SKIP_FILES:
            skipped += 1
            continue

        try:
            data      = tbd_path.read_bytes()
            chunks, _ = parse_riff(data)
        except Exception:
            skipped += 1
            continue

        mode = classify(tbd_path, chunks)

        if mode == 'skip':
            skipped += 1
            continue

        if mode in ('simple', 'surgical'):
            strings = extract_via_impt(chunks, mode)
        elif mode == 'hybrid':
            strings = extract_hybrid(chunks)
        elif mode == 'gobjects':
            strings = extract_gobjects(chunks)
        else:
            strings = extract_inplace_raw(chunks, mode)

        strings = [s for s in strings if len(s['original'].strip()) >= 3]
        if not strings:
            skipped += 1
            continue

        all_files[rel]  = strings
        total_strs     += len(strings)
        label = MODO_LABEL_FILE.get(mode, mode)
        print(f"  [{label}] {rel}: {len(strings)} strings")

    print(f"\n  LIVRE   = qualquer tamanho, acentos livres")
    print(f"  HIBRID. = IMPT livre + embutidas com limite (Menu.tbd)")
    print(f"  MISSAO  = gobjects.tbd (Log Entry, objetivos, dicas)")
    print(f"  LIMITE  = respeitar max_length em bytes")
    print(f"\n  Arquivos com strings : {len(all_files)}")
    print(f"  Arquivos ignorados   : {skipped}")
    print(f"  Total de strings     : {total_strs}")

    output = {
        "_info": {
            "ferramenta"    : "mf_tbd_tool_v4.py",
            "jogo"          : "Metal Fatigue (2000)",
            "instrucoes"    : (
                "Preencha 'translated' para cada string. "
                "max_length=-1: qualquer tamanho, acentos livres. "
                "max_length=N: maximo N bytes. "
                "Strings com translated==original sao ignoradas."
            ),
            "total_arquivos": len(all_files),
            "total_strings" : total_strs,
        },
        "arquivos": all_files,
    }

    out_path = folder / 'traducao_mf.json'
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nJSON gerado em:\n  {out_path}")
    print("\nProximo passo: edite 'translated' e rode o comando 'patch'.")


# ================================================================
# COMANDO: PATCH
# ================================================================

def cmd_patch(tbd_folder: str, json_path: str, output_folder: str):
    folder     = Path(tbd_folder)
    out_folder = Path(output_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    with open(json_path, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    files_data = jdata.get('arquivos', {})
    patched, unchanged, warnings = 0, 0, []

    print(f"Aplicando traducoes em {len(files_data)} arquivos...\n")

    for rel_path, strings in sorted(files_data.items()):
        orig_path = folder     / rel_path
        dest_path = out_folder / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if not orig_path.exists():
            warnings.append(f"Nao encontrado: {orig_path}")
            continue

        tmap    = {}
        changes = 0
        for entry in strings:
            o = entry.get('original',   '')
            t = entry.get('translated', o)
            if t and t != o:
                tmap[o] = t
                changes += 1

        if not changes:
            shutil.copy2(orig_path, dest_path)
            unchanged += 1
            continue

        try:
            orig_data = orig_path.read_bytes()
            chunks, _ = parse_riff(orig_data)
            mode      = classify(orig_path, chunks)

            if mode == 'skip':
                shutil.copy2(orig_path, dest_path)
                unchanged += 1
                continue

            if mode == 'simple':
                new_data = patch_simple(orig_data, tmap)
            elif mode == 'surgical':
                new_data = patch_surgical(orig_data, tmap)
            elif mode == 'hybrid':
                new_data = patch_hybrid(orig_data, tmap)
            elif mode == 'gobjects':
                new_data = patch_gobjects(orig_data, tmap)
            else:
                new_data = patch_inplace(orig_data, tmap)

            dest_path.write_bytes(new_data)

            diff  = len(new_data) - len(orig_data)
            sign  = '+' if diff >= 0 else ''
            label = MODO_LABEL_FILE.get(mode, mode)
            print(f"  [{label}] {rel_path}: {changes} strings ({sign}{diff} bytes)")
            patched += 1

        except Exception as e:
            warnings.append(f"ERRO em {rel_path}: {e}")
            shutil.copy2(orig_path, dest_path)

    print(f"\n  Arquivos traduzidos  : {patched}")
    print(f"  Sem alteracao        : {unchanged}")
    if warnings:
        print(f"\n  Avisos ({len(warnings)}):")
        for w in warnings:
            print(f"    {w}")
    print(f"\nSaida em: {out_folder}")
    print(f"\nProximo passo:")
    print(f"  xcopy \"{out_folder}\" \"{folder}\" /E /Y")


# ================================================================
# COMANDO: VERIFY
# ================================================================

def cmd_verify(tbd_folder: str, output_folder: str):
    folder     = Path(tbd_folder)
    out_folder = Path(output_folder)

    for out_path in sorted(out_folder.rglob('*.tbd')):
        rel       = out_path.relative_to(out_folder)
        orig_path = folder / rel
        if not orig_path.exists():
            continue
        orig_data = orig_path.read_bytes()
        new_data  = out_path.read_bytes()
        if orig_data == new_data:
            continue

        diff = len(new_data) - len(orig_data)
        print(f"\n{rel} ({diff:+d} bytes):")

        try:
            nc, _ = parse_riff(new_data)
        except Exception:
            continue

        dc   = nc.get('DATA', {}).get('data', b'')
        impt = nc.get('IMPT', {}).get('data', b'')

        shown = set()
        for i in range(0, len(impt) - 7, 8):
            off = int.from_bytes(impt[i:i+4], 'little')
            if off in shown or off >= len(dc):
                continue
            shown.add(off)
            raw = read_cstring(dc, off)
            if len(raw) >= 4:
                try:
                    txt = raw.decode('latin-1')
                    if re.search(r'[A-Za-z\u00C0-\u00FF]{2,}', txt):
                        print(f"  IMPT [{off:6d}] {repr(txt[:70])}")
                except Exception:
                    pass
        if not shown:
            i = 0
            while i < len(dc):
                j = i
                while j < len(dc) and dc[j] != 0x00:
                    j += 1
                raw = dc[i:j]
                if is_text(raw):
                    try:
                        print(f"  DATA [{i:6d}] {repr(raw.decode('latin-1')[:70])}")
                    except Exception:
                        pass
                i = j + 1


# ================================================================
# ENTRY POINT
# ================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == 'extract' and len(sys.argv) >= 3:
        cmd_extract(sys.argv[2])
    elif cmd == 'patch' and len(sys.argv) >= 5:
        cmd_patch(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'verify' and len(sys.argv) >= 4:
        cmd_verify(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
