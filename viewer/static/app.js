// ===== 全局状态 =====
let tileSize = 32;
let mapData = null;      // 当前地图数据
let activeTreeNode = null;
let treeIndex = new Map();
let showPassability = false;
let detailHistory = [];
let gamesPayload = null;
let activeGameId = '';
let activeGameName = '';
let encData = null;
let encCacheKey = '';
let assetMeta = null;
let assetMetaKey = '';
let iconSheetReady = false;
let mapBgImage = null;
let mapBgInfo = null;
let mapLoadToken = 0;
const spriteImageCache = new Map();
const characterAnimTimers = new WeakMap();
const tilesetImageCache = new Map();
let mapTileRender = {token: 0, status: 'idle', images: {}};
let mapEventSpriteRender = {token: 0, status: 'idle', sprites: []};
let floatingWindowSeq = 0;
let floatingWindowZ = 5600;
let floatingWindowDrag = null;

const canvas = document.getElementById('mapCanvas');
const ctx = canvas.getContext('2d');
const canvasWrap = document.getElementById('canvasWrap');
const mapBgStateEl = document.getElementById('mapBgState');
const gameSelect = document.getElementById('gameSelect');
const statusBar = document.getElementById('statusBar');
const gameModal = document.getElementById('gameModal');
const gameList = document.getElementById('gameList');
const registryWarning = document.getElementById('registryWarning');
const loadingModal = document.getElementById('loadingModal');
const loadingText = document.getElementById('loadingText');
const loadingProgressBar = document.getElementById('loadingProgressBar');
const loadingPercent = document.getElementById('loadingPercent');
const floatingWindowLayer = document.getElementById('floatingWindowLayer');

// ===== 详情面板历史 =====
function setStatus(text) {
  statusBar.textContent = text;
}

function setLoadingProgress(percent, text) {
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  if (text) loadingText.textContent = text;
  loadingProgressBar.style.width = p + '%';
  loadingPercent.textContent = Math.round(p) + '%';
}

function showLoading(text, percent) {
  loadingText.textContent = text || '正在加载...';
  setLoadingProgress(percent || 0);
  loadingModal.classList.remove('hidden');
}

function hideLoading() {
  loadingModal.classList.add('hidden');
  setLoadingProgress(0, '正在加载...');
}

function resetMapPanels() {
  mapData = null;
  activeTreeNode = null;
  treeIndex = new Map();
  showPassability = false;
  detailHistory = [];
  mapBgImage = null;
  mapBgInfo = null;
  mapLoadToken += 1;
  mapTileRender = {token: mapLoadToken, status: 'idle', images: {}};
  mapEventSpriteRender = {token: mapLoadToken, status: 'idle', sprites: []};
  document.getElementById('mapTitle').textContent = '未选择';
  document.getElementById('mapSize').textContent = '-';
  mapBgStateEl.textContent = '-';
  document.getElementById('zoomLevel').textContent = tileSize;
  document.getElementById('passToggle').classList.toggle('active', false);
  document.getElementById('treeWrap').innerHTML = '';
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  canvas.width = 0;
  canvas.height = 0;
}

function showNoGameState(message) {
  resetMapPanels();
  closeAllFloatingWindows();
  const dc = document.getElementById('detailContent');
  dc.innerHTML = '<div class="no-game">' +
    '<div style="font-size:42px;opacity:.35">🎮</div>' +
    '<div>' + esc(message || '当前没有可用游戏，请先拖拽 EXE 到 game_tool.bat 或在上方“管理游戏库”中添加。') + '</div>' +
    '</div>';
}

async function apiJson(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (e) {
    throw new Error('网络请求失败: ' + (e && e.message ? e.message : e));
  }
  let payload = null;
  try {
    payload = await res.json();
  } catch (e) {
    payload = null;
  }
  if (!res.ok) {
    const msg = (payload && payload.error) ? payload.error : ('请求失败: HTTP ' + res.status);
    throw new Error(msg);
  }
  if (payload && payload.error) {
    throw new Error(payload.error);
  }
  return payload;
}

async function apiText(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (e) {
    throw new Error('网络请求失败: ' + (e && e.message ? e.message : e));
  }
  const text = await res.text();
  if (!res.ok) throw new Error(text || ('请求失败: HTTP ' + res.status));
  return text;
}

function pushDetail(html) {
  const dc = document.getElementById('detailContent');
  if (dc.innerHTML && !dc.innerHTML.includes('empty-state') && !dc.innerHTML.includes('请稍候')) {
    detailHistory.push(dc.innerHTML);
    if (detailHistory.length > 50) detailHistory.shift();
  }
  dc.innerHTML = html;
  document.getElementById('backBtn').style.display = detailHistory.length ? 'inline-block' : 'none';
}
function goBack() {
  if (!detailHistory.length) return;
  const dc = document.getElementById('detailContent');
  dc.innerHTML = detailHistory.pop();
  document.getElementById('backBtn').style.display = detailHistory.length ? 'inline-block' : 'none';
}

// ===== 地图树 =====
function getCoverSrc(raw) {
  const cover = (raw || '').trim();
  if (!cover) return '';
  if (/^https?:\/\//i.test(cover) || cover.startsWith('/')) return cover;
  return '/api/cover?path=' + encodeURIComponent(cover);
}

function engineLabel(engine) {
  const e = String(engine || '').toLowerCase();
  if (e === 'vxace') return 'VX Ace';
  if (e === 'vx') return 'VX';
  return 'MV/MZ';
}

function getActiveGameEntry() {
  const games = (gamesPayload && gamesPayload.games) ? gamesPayload.games : [];
  return games.find(g => g.id === activeGameId) || null;
}

function buildEncCacheKey(game) {
  if (!game) return '';
  return String(game.id || '') + '::' + String(game.updated_at || '');
}

function invalidateEncyclopediaCache() {
  encData = null;
  encCacheKey = '';
  encSelIdx = -1;
}

function invalidateAssetMetaCache() {
  assetMeta = null;
  assetMetaKey = '';
  iconSheetReady = false;
}

function getAssetMetaKey(game) {
  if (!game) return '';
  return String(game.id || '') + '::' + String(game.updated_at || '');
}

async function ensureAssetMeta(force) {
  const active = getActiveGameEntry();
  if (!active) {
    invalidateAssetMetaCache();
    return null;
  }
  const key = getAssetMetaKey(active);
  if (!force && assetMeta && assetMetaKey === key) return assetMeta;

  assetMeta = await apiJson('/api/assets/meta');
  assetMetaKey = key;
  iconSheetReady = false;

  if (assetMeta && assetMeta.iconset_url) {
    const img = new Image();
    img.onload = function() {
      iconSheetReady = true;
      if (encData) {
        renderEncList();
        if (encSelIdx >= 0) showEncDetail(encSelIdx);
      }
    };
    img.onerror = function() {
      iconSheetReady = false;
    };
    img.src = assetMeta.iconset_url;
  }
  return assetMeta;
}

function iconHtml(iconIndex, extraClass) {
  const idx = Number(iconIndex || 0);
  const cls = extraClass ? (' ' + extraClass) : '';
  if (!assetMeta || !assetMeta.iconset_url || idx <= 0) {
    return '<span class="pixel-icon empty' + cls + '"></span>';
  }
  const size = Number(assetMeta.icon_size || 24);
  const columns = Number(assetMeta.icon_columns || 16);
  const x = -((idx % columns) * size);
  const y = -(Math.floor(idx / columns) * size);
  const bg = escAttr(assetMeta.iconset_url);
  if (!iconSheetReady) {
    return '<span class="pixel-icon skeleton' + cls + '" style="width:' + size + 'px;height:' + size + 'px"></span>';
  }
  return '<span class="pixel-icon' + cls + '" style="width:' + size + 'px;height:' + size + 'px;background-image:url(&quot;' + bg + '&quot;);background-position:' + x + 'px ' + y + 'px"></span>';
}

function renderGameSelect() {
  const games = (gamesPayload && gamesPayload.games) ? gamesPayload.games : [];
  gameSelect.innerHTML = '';
  if (!games.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '无游戏';
    gameSelect.appendChild(opt);
    gameSelect.disabled = true;
    activeGameId = '';
    activeGameName = '';
    return;
  }
  games.forEach(game => {
    const opt = document.createElement('option');
    opt.value = game.id;
    const mark = game.is_available ? '' : ' (路径失效)';
    opt.textContent = game.name + ' [' + engineLabel(game.engine) + ']' + mark;
    gameSelect.appendChild(opt);
  });
  activeGameId = gamesPayload.active_game_id || '';
  if (activeGameId) gameSelect.value = activeGameId;
  if (!gameSelect.value && games.length) gameSelect.value = games[0].id;
  const active = games.find(g => g.id === gameSelect.value);
  activeGameId = active ? active.id : '';
  activeGameName = active ? active.name : '';
  gameSelect.disabled = false;
}

async function loadGames(tryLoadTree) {
  try {
    gamesPayload = await apiJson('/api/games');
  } catch (e) {
    gamesPayload = {games: [], active_game_id: '', warning: ''};
    invalidateEncyclopediaCache();
    invalidateAssetMetaCache();
    setStatus('加载游戏库失败: ' + e.message);
    showNoGameState('无法读取游戏库，请检查后端日志。');
    return;
  }

  renderGameSelect();
  if (gamesPayload.warning) {
    registryWarning.textContent = gamesPayload.warning;
    registryWarning.style.display = '';
  } else {
    registryWarning.textContent = '';
    registryWarning.style.display = 'none';
  }

  const active = (gamesPayload.games || []).find(g => g.id === activeGameId);
  if (!active) {
    invalidateEncyclopediaCache();
    invalidateAssetMetaCache();
    setStatus('当前没有已选择游戏');
    showNoGameState();
    return;
  }

  const nextEncKey = buildEncCacheKey(active);
  if (encCacheKey && encCacheKey !== nextEncKey) {
    invalidateEncyclopediaCache();
  }
  if (assetMetaKey && assetMetaKey !== getAssetMetaKey(active)) {
    invalidateAssetMetaCache();
  }

  activeGameName = active.name;
  if (!active.is_available) {
    setStatus('当前游戏路径失效，请在“管理游戏库”里修复或重新添加');
    showNoGameState('当前游戏路径失效，请在“管理游戏库”中删除或重新添加。');
    return;
  }

  try {
    await ensureAssetMeta(false);
  } catch (e) {
    invalidateAssetMetaCache();
    setStatus('资源元数据加载失败: ' + e.message);
  }

  setStatus('当前游戏: ' + active.name);
  if (tryLoadTree) {
    await loadTree();
  }
}

async function selectGame(gameId) {
  if (!gameId) return;
  const current = ((gamesPayload && gamesPayload.games) || []).find(g => g.id === gameId);
  const targetName = current ? current.name : '目标游戏';
  closeAllFloatingWindows();

  showLoading('正在加载「' + targetName + '」...', 0);
  try {
    setLoadingProgress(15, '正在切换活动游戏...');
    await apiJson('/api/games/select', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({game_id: gameId})
    });
    setLoadingProgress(45, '正在同步游戏信息...');
    await loadGames(false);
    setLoadingProgress(70, '正在重置地图面板...');
    resetMapPanels();

    const loaded = ((gamesPayload && gamesPayload.games) || []).find(g => g.id === gameId);
    const loadedName = loaded ? loaded.name : targetName;
    setLoadingProgress(88, '正在跳转到「' + loadedName + '」...');
    await loadTree();
    setLoadingProgress(100, '加载完成');
    hideLoading();
    setStatus('已切换到: ' + loadedName);
  } catch (e) {
    hideLoading();
    alert('切换游戏失败: ' + e.message);
    setStatus('切换游戏失败: ' + e.message);
  }
}

function renderGameManager() {
  const games = (gamesPayload && gamesPayload.games) ? gamesPayload.games : [];
  if (!games.length) {
    gameList.innerHTML = '<div style="color:var(--text2)">暂无游戏。请先拖拽 EXE 到 game_tool.bat。</div>';
    return;
  }
  let html = '';
  games.forEach(game => {
    const coverSrc = getCoverSrc(game.cover_image);
    const activeTag = game.is_active ? ' <span style="color:#51cf66">(当前)</span>' : '';
    const badTag = game.is_available ? '' : ' <span style="color:#ff8787">(路径失效)</span>';
    html += '<div class="game-card' + (game.is_available ? '' : ' unavailable') + '">';
    if (coverSrc) {
      html += '<div class="game-cover" style="background-image:url(\'' + coverSrc.replace(/'/g, '\\\'') + '\')"></div>';
    } else {
      html += '<div class="game-cover">未设置封面</div>';
    }
    html += '<div class="game-meta">';
    html += '<div class="game-title">' + esc(game.name) + activeTag + badTag + '</div>';
    html += '<div class="game-path"><b>ENGINE:</b> ' + esc(engineLabel(game.engine)) + '</div>';
    html += '<div class="game-path"><b>EXE:</b> ' + esc(game.exe_path) + '</div>';
    html += '<div class="game-path"><b>DATA:</b> ' + esc(game.data_path) + '</div>';
    html += '<div class="game-actions">';
    html += '<button class="primary" type="button" onclick="uiSelectGame(\'' + game.id + '\')">设为当前</button>';
    html += '<button type="button" onclick="uiRenameGame(\'' + game.id + '\')">改名</button>';
    html += '<button type="button" onclick="uiSetCover(\'' + game.id + '\')">设置封面</button>';
    html += '<button type="button" onclick="uiClearCover(\'' + game.id + '\')">清空封面</button>';
    html += '<button class="danger" type="button" onclick="uiDeleteGame(\'' + game.id + '\')">删除</button>';
    html += '</div></div></div>';
  });
  gameList.innerHTML = html;
}

function openGameManager() {
  renderGameManager();
  gameModal.classList.remove('hidden');
}

function closeGameManager() {
  gameModal.classList.add('hidden');
}

async function patchGame(gameId, payload) {
  await apiJson('/api/games/' + encodeURIComponent(gameId), {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  await loadGames(false);
  renderGameManager();
}

async function uiSelectGame(gameId) {
  await selectGame(gameId);
  renderGameManager();
}

async function uiRenameGame(gameId) {
  const current = ((gamesPayload && gamesPayload.games) || []).find(g => g.id === gameId);
  const next = prompt('请输入新名称', current ? current.name : '');
  if (next === null) return;
  const name = String(next || '').trim();
  if (!name) {
    alert('名称不能为空');
    return;
  }
  try {
    await patchGame(gameId, {name});
  } catch (e) {
    alert('改名失败: ' + e.message);
  }
}

async function uiSetCover(gameId) {
  const next = prompt('请输入封面地址（本地绝对路径或 http(s) URL）');
  if (next === null) return;
  try {
    await patchGame(gameId, {cover_image: String(next || '').trim()});
  } catch (e) {
    alert('设置封面失败: ' + e.message);
  }
}

async function uiClearCover(gameId) {
  try {
    await patchGame(gameId, {cover_image: ''});
  } catch (e) {
    alert('清空封面失败: ' + e.message);
  }
}

async function uiDeleteGame(gameId) {
  if (!confirm('确认删除该游戏记录？')) return;
  try {
    await apiJson('/api/games/' + encodeURIComponent(gameId), {method: 'DELETE'});
    await loadGames(true);
    renderGameManager();
  } catch (e) {
    alert('删除失败: ' + e.message);
  }
}

async function uiRegisterExePath() {
  const input = document.getElementById('registerExeInput');
  const exePath = (input.value || '').trim();
  if (!exePath) {
    alert('请输入 EXE 全路径');
    return;
  }
  try {
    const resp = await apiJson('/api/games/register-exe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({exe_path: exePath, make_active: true})
    });
    input.value = '';
    invalidateEncyclopediaCache();
    invalidateAssetMetaCache();
    await loadGames(true);
    renderGameManager();
    const refreshTip = ' 数据已更新，图鉴将重新加载。';
    if (resp && resp.prepare_result && resp.prepare_result.message) {
      setStatus(resp.prepare_result.message + refreshTip);
    } else {
      setStatus('已添加游戏: ' + exePath + '。' + refreshTip.trim());
    }
  } catch (e) {
    alert('添加失败: ' + e.message);
  }
}

async function uiPickExeByDialog() {
  try {
    const resp = await apiJson('/api/games/pick-exe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({make_active: true})
    });
    if (resp && resp.cancelled) {
      setStatus('已取消选择 EXE');
      return;
    }
    invalidateEncyclopediaCache();
    invalidateAssetMetaCache();
    await loadGames(true);
    renderGameManager();
    const refreshTip = ' 数据已更新，图鉴将重新加载。';
    if (resp && resp.prepare_result && resp.prepare_result.message) {
      setStatus(resp.prepare_result.message + refreshTip);
    } else if (resp && resp.game && resp.game.name) {
      setStatus('已添加游戏: ' + resp.game.name + '。' + refreshTip.trim());
    }
  } catch (e) {
    alert('打开选择窗口失败: ' + e.message);
    setStatus('打开选择窗口失败: ' + e.message);
  }
}

async function loadTree() {
  try {
    const tree = await apiJson('/api/tree');
    treeIndex = new Map();
    const wrap = document.getElementById('treeWrap');
    wrap.innerHTML = '';
    renderTree(tree, wrap, 0);
    if (!tree.length) {
      setStatus('当前游戏没有地图数据');
      showNoGameState('当前游戏地图列表为空。');
      return;
    }
    setStatus('当前游戏: ' + activeGameName + '，请选择地图');
  } catch (e) {
    setStatus('加载地图树失败: ' + e.message);
    showNoGameState('加载地图树失败：' + e.message);
  }
}

function renderTree(nodes, container, depth) {
  nodes.forEach(node => {
    const div = document.createElement('div');
    div.className = 'tree-node';

    const label = document.createElement('div');
    label.className = 'tree-label';
    const hasChildren = node.children && node.children.length > 0;

    const arrow = document.createElement('span');
    arrow.className = 'arrow' + (hasChildren ? '' : ' empty');
    arrow.textContent = '\u25B6';

    const idSpan = document.createElement('span');
    idSpan.className = 'id';
    idSpan.textContent = String(node.id).padStart(3, '0');

    const nameSpan = document.createElement('span');
    nameSpan.textContent = node.name;

    label.append(arrow, idSpan, nameSpan);
    div.appendChild(label);
    label.dataset.mapId = String(node.id);
    treeIndex.set(String(node.id), label);

    let childrenDiv = null;
    if (hasChildren) {
      childrenDiv = document.createElement('div');
      childrenDiv.className = 'tree-children';
      renderTree(node.children, childrenDiv, depth + 1);
      div.appendChild(childrenDiv);
    }

    label.addEventListener('click', (e) => {
      e.stopPropagation();
      // 切换展开/折叠
      if (hasChildren) {
        const isOpen = childrenDiv.classList.toggle('open');
        arrow.classList.toggle('open', isOpen);
      }
      // 加载地图
      if (activeTreeNode) activeTreeNode.classList.remove('active');
      label.classList.add('active');
      activeTreeNode = label;
      loadMap(node.id);
    });

    container.appendChild(div);
  });
}

function activateTreeNode(mapId) {
  const key = String(mapId);
  const label = treeIndex.get(key);
  if (!label) return;
  if (activeTreeNode) activeTreeNode.classList.remove('active');
  label.classList.add('active');
  activeTreeNode = label;

  // 展开祖先节点
  let nodeDiv = label.parentElement;
  while (nodeDiv) {
    const parentChildren = nodeDiv.parentElement;
    if (parentChildren && parentChildren.classList.contains('tree-children')) {
      parentChildren.classList.add('open');
      const parentNode = parentChildren.parentElement;
      if (parentNode) {
        const parentLabel = parentNode.querySelector(':scope > .tree-label');
        const arrow = parentLabel && parentLabel.querySelector('.arrow');
        if (arrow) arrow.classList.add('open');
      }
      nodeDiv = parentChildren.parentElement;
    } else {
      break;
    }
  }
  label.scrollIntoView({block: 'nearest'});
}

// ===== 搜索过滤 =====
document.getElementById('searchInput').addEventListener('input', function() {
  const kw = this.value.trim().toLowerCase();
  filterTree(document.getElementById('treeWrap'), kw);
});

function filterTree(container, kw) {
  let hasMatch = false;
  for (const node of container.children) {
    const label = node.querySelector(':scope > .tree-label');
    const children = node.querySelector(':scope > .tree-children');
    const text = label ? label.textContent.toLowerCase() : '';
    let childMatch = false;
    if (children) childMatch = filterTree(children, kw);
    const match = !kw || text.includes(kw) || childMatch;
    node.style.display = match ? '' : 'none';
    if (match && kw && children) {
      children.classList.add('open');
      const arrow = label.querySelector('.arrow');
      if (arrow) arrow.classList.add('open');
    }
    if (match) hasMatch = true;
  }
  return hasMatch;
}

// ===== 地图加载与渲染 =====
function setMapBackgroundState(text) {
  mapBgStateEl.textContent = text || '-';
}

function updateMapSizeLabel() {
  const el = document.getElementById('mapSize');
  if (!mapData) {
    el.textContent = '-';
    return;
  }
  const w = Number(mapData.width || 0);
  const h = Number(mapData.height || 0);
  el.textContent = w + ' x ' + h + '（' + (w * tileSize) + ' x ' + (h * tileSize) + ' px）';
}

function startMapBackgroundLoad(background, token) {
  mapBgInfo = background || null;
  mapBgImage = null;
  if (!background || !background.status || background.status === 'none') {
    setMapBackgroundState('无');
    return;
  }
  if (background.status !== 'found' || !background.url) {
    setMapBackgroundState('缺失');
    if (background.message) setStatus(background.message);
    return;
  }
  setMapBackgroundState('加载中...');
  const img = new Image();
  img.onload = function() {
    if (token !== mapLoadToken) return;
    mapBgImage = img;
    setMapBackgroundState('已加载');
    renderMap();
  };
  img.onerror = function() {
    if (token !== mapLoadToken) return;
    mapBgImage = null;
    setMapBackgroundState('加载失败');
    if (mapBgInfo && mapBgInfo.message) setStatus(mapBgInfo.message);
    renderMap();
  };
  img.src = background.url;
}

function loadTilesetImageCached(src) {
  if (tilesetImageCache.has(src)) return tilesetImageCache.get(src);
  const p = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('tileset-load-failed'));
    img.src = src;
  });
  tilesetImageCache.set(src, p);
  return p;
}

function resolveTilesetSrc(name, key, engine) {
  const n = String(name || '').trim();
  if (!n) return '';
  const e = String(engine || '').toLowerCase();
  let rel = 'img/tilesets/' + n + '.png';
  if (e === 'vxace' || e === 'vx') {
    if (e === 'vx' && key && key[0] === 'A') {
      rel = 'Graphics/Autotiles/' + n + '.png';
    } else {
      rel = 'Graphics/Tilesets/' + n + '.png';
    }
  }
  return '/api/assets/file?rel=' + encodeURIComponent(rel);
}

function resolveTilesetSrcCandidates(name, key, engine) {
  const n = String(name || '').trim();
  if (!n) return [];
  const e = String(engine || '').toLowerCase();
  if (e === 'mv' || e === 'mz') {
    return [resolveTilesetSrc(n, key, e)];
  }
  if (e === 'vxace') {
    return [
      '/api/assets/file?rel=' + encodeURIComponent('Graphics/Tilesets/' + n + '.png'),
      '/api/assets/file?rel=' + encodeURIComponent('img/tilesets/' + n + '.png'),
    ];
  }
  if (e === 'vx') {
    const list = [];
    if (key && key[0] === 'A') {
      list.push('/api/assets/file?rel=' + encodeURIComponent('Graphics/Autotiles/' + n + '.png'));
    } else {
      list.push('/api/assets/file?rel=' + encodeURIComponent('Graphics/Tilesets/' + n + '.png'));
    }
    list.push('/api/assets/file?rel=' + encodeURIComponent('Graphics/Tilesets/' + n + '.png'));
    list.push('/api/assets/file?rel=' + encodeURIComponent('Graphics/Autotiles/' + n + '.png'));
    list.push('/api/assets/file?rel=' + encodeURIComponent('img/tilesets/' + n + '.png'));
    return list;
  }
  return [resolveTilesetSrc(n, key, e)];
}

async function loadFirstTilesetImage(srcList) {
  for (const src of srcList) {
    if (!src) continue;
    try {
      const img = await loadTilesetImageCached(src);
      return img;
    } catch (_e) {
      // fallback to next candidate
    }
  }
  return null;
}

function getEngineNativeTileSize() {
  const engine = String((mapData && mapData.engine) || '').toLowerCase();
  if (engine === 'mv' || engine === 'mz') return 48;
  return 32;
}

async function prepareMapTileRender(token) {
  const engine = String((mapData && mapData.engine) || '').toLowerCase();
  if (!mapData || (engine !== 'mv' && engine !== 'mz' && engine !== 'vx' && engine !== 'vxace') || !mapData.render) {
    mapTileRender = {token, status: 'idle', images: {}};
    return;
  }
  const render = mapData.render;
  const names = Array.isArray(render.tilesetNames) ? render.tilesetNames : [];
  const srcByKey = {
    A1: resolveTilesetSrcCandidates(names[0], 'A1', engine),
    A2: resolveTilesetSrcCandidates(names[1], 'A2', engine),
    A3: resolveTilesetSrcCandidates(names[2], 'A3', engine),
    A4: resolveTilesetSrcCandidates(names[3], 'A4', engine),
    A5: resolveTilesetSrcCandidates(names[4], 'A5', engine),
    B: resolveTilesetSrcCandidates(names[5], 'B', engine),
    C: resolveTilesetSrcCandidates(names[6], 'C', engine),
    D: resolveTilesetSrcCandidates(names[7], 'D', engine),
    E: resolveTilesetSrcCandidates(names[8], 'E', engine),
  };
  mapTileRender = {token, status: 'loading', images: {}};

  const tasks = Object.entries(srcByKey)
    .filter(([, srcList]) => Array.isArray(srcList) && srcList.length > 0)
    .map(async ([key, srcList]) => {
      const img = await loadFirstTilesetImage(srcList);
      return {key, img};
    });
  const loaded = await Promise.all(tasks);
  if (token !== mapLoadToken) return;

  const images = {};
  loaded.forEach(item => {
    if (item && item.img) images[item.key] = item.img;
  });
  mapTileRender = {token, status: 'ready', images};
  renderMap();
}

const MV_TILE_ID_B = 0;
const MV_TILE_ID_C = 256;
const MV_TILE_ID_D = 512;
const MV_TILE_ID_E = 768;
const MV_TILE_ID_A5 = 1536;
const MV_TILE_ID_A1 = 2048;
const MV_TILE_ID_A2 = 2816;
const MV_TILE_ID_A3 = 4352;
const MV_TILE_ID_A4 = 5888;
const MV_TILE_ID_MAX = 8192;
const TILESET_KEYS_BY_SET = ['A1', 'A2', 'A3', 'A4', 'A5', 'B', 'C', 'D', 'E'];

const FLOOR_AUTOTILE_TABLE = [
  [[2, 4], [1, 4], [2, 3], [1, 3]], [[2, 0], [1, 4], [2, 3], [1, 3]],
  [[2, 4], [3, 0], [2, 3], [1, 3]], [[2, 0], [3, 0], [2, 3], [1, 3]],
  [[2, 4], [1, 4], [2, 3], [3, 1]], [[2, 0], [1, 4], [2, 3], [3, 1]],
  [[2, 4], [3, 0], [2, 3], [3, 1]], [[2, 0], [3, 0], [2, 3], [3, 1]],
  [[2, 4], [1, 4], [2, 1], [1, 3]], [[2, 0], [1, 4], [2, 1], [1, 3]],
  [[2, 4], [3, 0], [2, 1], [1, 3]], [[2, 0], [3, 0], [2, 1], [1, 3]],
  [[2, 4], [1, 4], [2, 1], [3, 1]], [[2, 0], [1, 4], [2, 1], [3, 1]],
  [[2, 4], [3, 0], [2, 1], [3, 1]], [[2, 0], [3, 0], [2, 1], [3, 1]],
  [[0, 4], [1, 4], [0, 3], [1, 3]], [[0, 4], [3, 0], [0, 3], [1, 3]],
  [[0, 4], [1, 4], [0, 3], [3, 1]], [[0, 4], [3, 0], [0, 3], [3, 1]],
  [[2, 2], [1, 2], [2, 3], [1, 3]], [[2, 2], [1, 2], [2, 3], [3, 1]],
  [[2, 2], [1, 2], [2, 1], [1, 3]], [[2, 2], [1, 2], [2, 1], [3, 1]],
  [[2, 4], [3, 4], [2, 3], [3, 3]], [[2, 4], [3, 4], [2, 1], [3, 3]],
  [[2, 0], [3, 4], [2, 3], [3, 3]], [[2, 0], [3, 4], [2, 1], [3, 3]],
  [[2, 4], [1, 4], [2, 5], [1, 5]], [[2, 0], [1, 4], [2, 5], [1, 5]],
  [[2, 4], [3, 0], [2, 5], [1, 5]], [[2, 0], [3, 0], [2, 5], [1, 5]],
  [[0, 4], [3, 4], [0, 3], [3, 3]], [[2, 2], [1, 2], [2, 5], [1, 5]],
  [[0, 2], [1, 2], [0, 3], [1, 3]], [[0, 2], [1, 2], [0, 3], [3, 1]],
  [[2, 2], [3, 2], [2, 3], [3, 3]], [[2, 2], [3, 2], [2, 1], [3, 3]],
  [[2, 4], [3, 4], [2, 5], [3, 5]], [[2, 0], [3, 4], [2, 5], [3, 5]],
  [[0, 4], [1, 4], [0, 5], [1, 5]], [[0, 4], [3, 0], [0, 5], [1, 5]],
  [[0, 2], [3, 2], [0, 3], [3, 3]], [[0, 2], [1, 2], [0, 5], [1, 5]],
  [[0, 4], [3, 4], [0, 5], [3, 5]], [[2, 2], [3, 2], [2, 5], [3, 5]],
  [[0, 2], [3, 2], [0, 5], [3, 5]], [[0, 0], [1, 0], [0, 1], [1, 1]],
];

const WALL_AUTOTILE_TABLE = [
  [[2, 2], [1, 2], [2, 1], [1, 1]], [[0, 2], [1, 2], [0, 1], [1, 1]],
  [[2, 0], [1, 0], [2, 1], [1, 1]], [[0, 0], [1, 0], [0, 1], [1, 1]],
  [[2, 2], [3, 2], [2, 1], [3, 1]], [[0, 2], [3, 2], [0, 1], [3, 1]],
  [[2, 0], [3, 0], [2, 1], [3, 1]], [[0, 0], [3, 0], [0, 1], [3, 1]],
  [[2, 2], [1, 2], [2, 3], [1, 3]], [[0, 2], [1, 2], [0, 3], [1, 3]],
  [[2, 0], [1, 0], [2, 3], [1, 3]], [[0, 0], [1, 0], [0, 3], [1, 3]],
  [[2, 2], [3, 2], [2, 3], [3, 3]], [[0, 2], [3, 2], [0, 3], [3, 3]],
  [[2, 0], [3, 0], [2, 3], [3, 3]], [[0, 0], [3, 0], [0, 3], [3, 3]],
];

const WATERFALL_AUTOTILE_TABLE = [
  [[2, 0], [1, 0], [2, 1], [1, 1]], [[0, 0], [1, 0], [0, 1], [1, 1]],
  [[2, 0], [3, 0], [2, 1], [3, 1]], [[0, 0], [3, 0], [0, 1], [3, 1]],
];

function isVisibleTile(tileId) {
  return tileId > 0 && tileId < MV_TILE_ID_MAX;
}

function isAutotile(tileId) {
  return tileId >= MV_TILE_ID_A1;
}

function isTileA1(tileId) {
  return tileId >= MV_TILE_ID_A1 && tileId < MV_TILE_ID_A2;
}

function isTileA2(tileId) {
  return tileId >= MV_TILE_ID_A2 && tileId < MV_TILE_ID_A3;
}

function isTileA3(tileId) {
  return tileId >= MV_TILE_ID_A3 && tileId < MV_TILE_ID_A4;
}

function isTileA4(tileId) {
  return tileId >= MV_TILE_ID_A4 && tileId < MV_TILE_ID_MAX;
}

function isTileA5(tileId) {
  return tileId >= MV_TILE_ID_A5 && tileId < MV_TILE_ID_A1;
}

function getAutotileKind(tileId) {
  return Math.floor((tileId - MV_TILE_ID_A1) / 48);
}

function getAutotileShape(tileId) {
  return (tileId - MV_TILE_ID_A1) % 48;
}

function drawNormalTile(tileId, x, y, ts, images) {
  let setNumber = 0;
  if (isTileA5(tileId)) {
    setNumber = 4;
  } else {
    setNumber = 5 + Math.floor(tileId / 256);
  }
  const key = TILESET_KEYS_BY_SET[setNumber];
  const source = key ? images[key] : null;
  if (!source) return false;
  const srcTile = getEngineNativeTileSize();
  const sx = (Math.floor(tileId / 128) % 2 * 8 + tileId % 8) * srcTile;
  const sy = (Math.floor((tileId % 256) / 8) % 16) * srcTile;
  if (sx + srcTile > source.width || sy + srcTile > source.height) return false;
  ctx.drawImage(source, sx, sy, srcTile, srcTile, x * ts, y * ts, ts, ts);
  return true;
}

function drawAutotile(tileId, x, y, ts, images) {
  let autotileTable = FLOOR_AUTOTILE_TABLE;
  const kind = getAutotileKind(tileId);
  const shape = getAutotileShape(tileId);
  const tx = kind % 8;
  const ty = Math.floor(kind / 8);
  let bx = 0;
  let by = 0;
  let setNumber = 0;
  const animationFrame = 0;

  if (isTileA1(tileId)) {
    const waterSurfaceIndex = [0, 1, 2, 1][animationFrame % 4];
    setNumber = 0;
    if (kind === 0) {
      bx = waterSurfaceIndex * 2;
      by = 0;
    } else if (kind === 1) {
      bx = waterSurfaceIndex * 2;
      by = 3;
    } else if (kind === 2) {
      bx = 6;
      by = 0;
    } else if (kind === 3) {
      bx = 6;
      by = 3;
    } else {
      bx = Math.floor(tx / 4) * 8;
      by = ty * 6 + Math.floor(tx / 2) % 2 * 3;
      if (kind % 2 === 0) {
        bx += waterSurfaceIndex * 2;
      } else {
        bx += 6;
        autotileTable = WATERFALL_AUTOTILE_TABLE;
        by += animationFrame % 3;
      }
    }
  } else if (isTileA2(tileId)) {
    setNumber = 1;
    bx = tx * 2;
    by = (ty - 2) * 3;
  } else if (isTileA3(tileId)) {
    setNumber = 2;
    bx = tx * 2;
    by = (ty - 6) * 2;
    autotileTable = WALL_AUTOTILE_TABLE;
  } else if (isTileA4(tileId)) {
    setNumber = 3;
    bx = tx * 2;
    by = Math.floor((ty - 10) * 2.5 + (ty % 2 === 1 ? 0.5 : 0));
    if (ty % 2 === 1) autotileTable = WALL_AUTOTILE_TABLE;
  } else {
    return false;
  }

  const table = autotileTable[shape];
  const key = TILESET_KEYS_BY_SET[setNumber];
  const source = key ? images[key] : null;
  if (!table || !source) return false;

  const srcTile = getEngineNativeTileSize();
  const w1 = srcTile / 2;
  const h1 = srcTile / 2;
  const dw1 = ts / 2;
  const dh1 = ts / 2;
  for (let i = 0; i < 4; i++) {
    const qsx = table[i][0];
    const qsy = table[i][1];
    const sx1 = (bx * 2 + qsx) * w1;
    const sy1 = (by * 2 + qsy) * h1;
    const dx1 = x * ts + (i % 2) * dw1;
    const dy1 = y * ts + Math.floor(i / 2) * dh1;
    if (sx1 + w1 > source.width || sy1 + h1 > source.height) continue;
    ctx.drawImage(source, sx1, sy1, w1, h1, dx1, dy1, dw1, dh1);
  }
  return true;
}

function drawTileById(tileId, x, y, ts, images) {
  if (!isVisibleTile(tileId)) return false;
  if (isAutotile(tileId)) return drawAutotile(tileId, x, y, ts, images);
  return drawNormalTile(tileId, x, y, ts, images);
}

function drawShadowLayer(data, w, h, layerSize, ts) {
  if (!Array.isArray(data) || data.length < layerSize * 5) return;
  const shadowBase = layerSize * 4;
  const w1 = ts / 2;
  const h1 = ts / 2;
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const bits = Number(data[shadowBase + y * w + x] || 0) & 0x0f;
      if (!bits) continue;
      for (let i = 0; i < 4; i++) {
        if (bits & (1 << i)) {
          const dx = x * ts + (i % 2) * w1;
          const dy = y * ts + Math.floor(i / 2) * h1;
          ctx.fillRect(dx, dy, w1, h1);
        }
      }
    }
  }
}

function drawMapTileObjects(ts) {
  if (!mapData || !mapData.render || !Array.isArray(mapData.render.data)) return;
  if (mapTileRender.status !== 'ready') return;
  const images = mapTileRender.images || {};
  const w = Number(mapData.width || 0);
  const h = Number(mapData.height || 0);
  if (!w || !h) return;
  const data = mapData.render.data;
  const layerSize = w * h;
  if (layerSize <= 0 || data.length < layerSize) return;
  const totalLayers = Math.max(1, Math.floor(data.length / layerSize));
  const drawLayers = Math.min(4, totalLayers);

  // 按地图层顺序绘制完整瓦片内容（地板+物件）
  for (let z = 0; z < drawLayers; z++) {
    const base = z * layerSize;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const tileId = Number(data[base + y * w + x] || 0);
        if (!tileId) continue;
        drawTileById(tileId, x, y, ts, images);
      }
    }
  }
  if (totalLayers >= 5) {
    drawShadowLayer(data, w, h, layerSize, ts);
  }
}

function drawScaledBackgroundPattern(img, width, height, scale) {
  if (!img || !width || !height) return false;
  const s = Number.isFinite(scale) && scale > 0 ? scale : 1;
  ctx.save();
  ctx.globalAlpha = 0.72;
  if (s !== 1) ctx.scale(s, s);
  const pattern = ctx.createPattern(img, 'repeat');
  if (!pattern) {
    ctx.restore();
    return false;
  }
  ctx.fillStyle = pattern;
  ctx.fillRect(0, 0, width / s, height / s);
  ctx.restore();
  return true;
}

function pickEventFirstVisual(evt) {
  if (!evt || !Array.isArray(evt.pages) || !evt.pages.length) return null;
  const firstPage = evt.pages[0];
  if (!firstPage || typeof firstPage !== 'object') return null;
  const visual = firstPage.visual;
  if (!visual || typeof visual !== 'object') return null;
  const characterName = String(visual.characterName || '').trim();
  if (!characterName) return null;
  return {
    characterName: characterName,
    characterIndex: clampInt(visual.characterIndex, 0, 0, 7),
    direction: clampInt(visual.direction, 2, 2, 8),
    pattern: clampInt(visual.pattern, 1, 0, 2),
    isBigCharacter: !!visual.isBigCharacter,
  };
}

function computeCharacterFrame(img, visual) {
  if (!img || !visual) return null;
  const directionRowMap = {2: 0, 4: 1, 6: 2, 8: 3};
  const isBig = !!visual.isBigCharacter;
  const characterIndex = clampInt(visual.characterIndex, 0, 0, 7);
  const pattern = clampInt(visual.pattern, 1, 0, 2);
  const direction = clampInt(visual.direction, 2, 2, 8);
  const dirRow = directionRowMap[direction] !== undefined ? directionRowMap[direction] : 0;
  const columns = isBig ? 3 : 12;
  const rows = isBig ? 4 : 8;
  const cellW = Math.floor(img.width / columns);
  const cellH = Math.floor(img.height / rows);
  if (cellW <= 0 || cellH <= 0) return null;
  const blockX = isBig ? 0 : (characterIndex % 4) * (cellW * 3);
  const blockY = isBig ? 0 : Math.floor(characterIndex / 4) * (cellH * 4);
  const sx = blockX + pattern * cellW;
  const sy = blockY + dirRow * cellH;
  if (sx + cellW > img.width || sy + cellH > img.height) return null;
  return {sx, sy, sw: cellW, sh: cellH};
}

async function prepareMapEventSprites(token) {
  if (!mapData || !Array.isArray(mapData.events) || !mapData.events.length) {
    mapEventSpriteRender = {token, status: 'idle', sprites: []};
    return;
  }

  const tasks = [];
  mapData.events.forEach(evt => {
    if (!evt || typeof evt !== 'object') return;
    const visual = pickEventFirstVisual(evt);
    if (!visual) return;
    const src = resolveVisualUrl('character', visual.characterName);
    if (!src) return;
    tasks.push({evt, visual, src});
  });

  if (!tasks.length) {
    mapEventSpriteRender = {token, status: 'ready', sprites: []};
    return;
  }

  mapEventSpriteRender = {token, status: 'loading', sprites: []};
  const loaded = await Promise.all(tasks.map(async item => {
    try {
      const img = await loadImageCached(item.src);
      return {evt: item.evt, visual: item.visual, img};
    } catch (_e) {
      return null;
    }
  }));
  if (token !== mapLoadToken) return;
  const sprites = loaded.filter(item => !!item);
  mapEventSpriteRender = {token, status: 'ready', sprites};
  renderMap();
}

function drawMapEventSprites(ts) {
  if (!mapData || mapEventSpriteRender.status !== 'ready' || !Array.isArray(mapEventSpriteRender.sprites)) return;
  if (!mapEventSpriteRender.sprites.length) return;

  ctx.save();
  ctx.imageSmoothingEnabled = false;
  mapEventSpriteRender.sprites.forEach(item => {
    if (!item || !item.evt || !item.img) return;
    const gx = Number(item.evt.x || 0);
    const gy = Number(item.evt.y || 0);
    if (!Number.isFinite(gx) || !Number.isFinite(gy)) return;
    const frame = computeCharacterFrame(item.img, item.visual);
    if (!frame) return;
    const dw = Math.max(8, Math.round(ts * 1.05));
    const dh = Math.max(8, Math.round(ts * 1.2));
    const dx = gx * ts + Math.floor((ts - dw) / 2);
    const dy = gy * ts + (ts - dh);
    ctx.drawImage(item.img, frame.sx, frame.sy, frame.sw, frame.sh, dx, dy, dw, dh);
  });
  ctx.restore();
}

async function loadMap(mapId) {
  mapLoadToken += 1;
  const currentToken = mapLoadToken;
  setStatus('加载中...');
  try {
    mapData = await apiJson('/api/map/' + mapId);
  } catch (e) {
    setStatus('地图加载失败: ' + e.message);
    return;
  }
  document.getElementById('mapTitle').textContent = mapData.name;
  updateMapSizeLabel();
  setStatus(mapData.name + ' — ' + mapData.events.length + ' 个事件');
  startMapBackgroundLoad(mapData.background, currentToken);
  prepareMapTileRender(currentToken);
  prepareMapEventSprites(currentToken);
  activateTreeNode(mapId);
  renderMap();
  showMapInfo();
}

function focusMapCell(x, y) {
  if (!mapData) return;
  const ts = tileSize;
  const cx = x * ts + ts / 2;
  const cy = y * ts + ts / 2;
  const maxScrollX = Math.max(0, canvas.width - canvasWrap.clientWidth);
  const maxScrollY = Math.max(0, canvas.height - canvasWrap.clientHeight);
  let sx = Math.max(0, cx - canvasWrap.clientWidth / 2);
  let sy = Math.max(0, cy - canvasWrap.clientHeight / 2);
  canvasWrap.scrollLeft = Math.min(maxScrollX, sx);
  canvasWrap.scrollTop = Math.min(maxScrollY, sy);
}

function renderMap() {
  if (!mapData) return;
  const w = mapData.width, h = mapData.height, ts = tileSize;
  canvas.width = w * ts;
  canvas.height = h * ts;

  // 背景底图（异步加载完成后会自动二次重绘）
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (mapBgImage) {
    const bgScale = tileSize / getEngineNativeTileSize();
    const ok = drawScaledBackgroundPattern(mapBgImage, canvas.width, canvas.height, bgScale);
    if (!ok) {
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          ctx.fillStyle = (x + y) % 2 === 0 ? '#1e1e30' : '#1a1a2a';
          ctx.fillRect(x * ts, y * ts, ts, ts);
        }
      }
    }
  } else {
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        ctx.fillStyle = (x + y) % 2 === 0 ? '#1e1e30' : '#1a1a2a';
        ctx.fillRect(x * ts, y * ts, ts, ts);
      }
    }
  }

  // 异步叠加地图上层物件（瓦片资源就绪后自动绘制）
  drawMapTileObjects(ts);

  // 网格线
  ctx.strokeStyle = '#252540';
  for (let x = 0; x <= w; x++) {
    ctx.beginPath(); ctx.moveTo(x*ts, 0); ctx.lineTo(x*ts, h*ts); ctx.stroke();
  }
  for (let y = 0; y <= h; y++) {
    ctx.beginPath(); ctx.moveTo(0, y*ts); ctx.lineTo(w*ts, y*ts); ctx.stroke();
  }

  // 绘制通行度叠加层
  if (showPassability && mapData.passability) {
    const pass = mapData.passability;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const p = pass[y * w + x];
        if (p === 0) {
          ctx.fillStyle = 'rgba(255,60,60,0.35)';
        } else {
          ctx.fillStyle = 'rgba(60,255,100,0.12)';
        }
        ctx.fillRect(x * ts, y * ts, ts, ts);
      }
    }
  }

  // 异步叠加事件第一页角色帧（无素材时自动跳过）
  drawMapEventSprites(ts);

  // 事件类型视觉映射
  const EVT_STYLE = {
    treasure: {color:'#ffd43b', glow:'255,212,59', symbol:'$'},
    transfer: {color:'#74b9ff', glow:'116,185,255', symbol:'\u2192'},
    battle:   {color:'#ff6b6b', glow:'255,107,107', symbol:'!'},
    dialog:   {color:'#51cf66', glow:'81,207,102',  symbol:'T'},
    other:    {color:'#636e72', glow:'99,110,114',   symbol:'\u00b7'}
  };

  // 绘制事件标记
  mapData.events.forEach(evt => {
    const ex = evt.x * ts, ey = evt.y * ts;
    const st = EVT_STYLE[evt.type] || EVT_STYLE.other;
    // 发光效果
    const grd = ctx.createRadialGradient(
      ex + ts/2, ey + ts/2, ts*0.1, ex + ts/2, ey + ts/2, ts*0.7);
    grd.addColorStop(0, 'rgba('+st.glow+',0.4)');
    grd.addColorStop(1, 'rgba('+st.glow+',0)');
    ctx.fillStyle = grd;
    ctx.fillRect(ex - ts*0.2, ey - ts*0.2, ts*1.4, ts*1.4);
    // 彩色方块
    ctx.fillStyle = st.color;
    const pad = Math.max(2, ts * 0.12);
    ctx.beginPath();
    roundRect(ctx, ex+pad, ey+pad, ts-pad*2, ts-pad*2, 3);
    ctx.fill();
    // 类型符号
    if (ts >= 16) {
      ctx.fillStyle = evt.type === 'other' ? '#ccc' : '#fff';
      ctx.font = 'bold ' + Math.max(8, ts*0.4|0) + 'px Arial';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(st.symbol, ex + ts/2, ey + ts/2);
    }
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

// ===== 缩放 =====
function zoom(delta) {
  tileSize = Math.max(8, Math.min(64, tileSize + delta));
  document.getElementById('zoomLevel').textContent = tileSize;
  updateMapSizeLabel();
  renderMap();
}
canvasWrap.addEventListener('wheel', e => {
  e.preventDefault();
  zoom(e.deltaY < 0 ? 4 : -4);
}, {passive: false});

// ===== 通行度开关 =====
function togglePassability() {
  showPassability = !showPassability;
  document.getElementById('passToggle').classList.toggle('active', showPassability);
  renderMap();
}

// ===== 导出攻略 =====
function downloadText(filename, text) {
  const blob = new Blob([text], {type: 'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportGuide(allMaps) {
  const url = allMaps ? '/api/export?all=1' : ('/api/export?map=' + mapData.id);
  setStatus('正在导出...');
  try {
    const text = await apiText(url);
    const filename = allMaps
      ? 'rpgmv_guide_all.md'
      : ('rpgmv_guide_map_' + String(mapData.id).padStart(3, '0') + '.md');
    downloadText(filename, text);
    setStatus('导出完成');
  } catch (e) {
    alert('导出失败: ' + (e && e.message ? e.message : e));
    setStatus('导出失败');
  }
}

function exportGuidePrompt() {
  const wantAll = confirm('是否导出全部地图？\n确定: 全部地图\n取消: 当前地图');
  if (!wantAll && !mapData) {
    alert('请先选择地图');
    return;
  }
  exportGuide(wantAll);
}

// ===== 拖拽平移 =====
let isDragging = false, wasDragged = false;
let dragStartX = 0, dragStartY = 0, scrollStartX = 0, scrollStartY = 0;

canvasWrap.addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  isDragging = true; wasDragged = false;
  dragStartX = e.clientX; dragStartY = e.clientY;
  scrollStartX = canvasWrap.scrollLeft; scrollStartY = canvasWrap.scrollTop;
  canvasWrap.classList.add('dragging');
});

window.addEventListener('mousemove', e => {
  if (!isDragging) return;
  const dx = e.clientX - dragStartX, dy = e.clientY - dragStartY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;
  canvasWrap.scrollLeft = scrollStartX - dx;
  canvasWrap.scrollTop = scrollStartY - dy;
});

window.addEventListener('mouseup', () => {
  if (!isDragging) return;
  isDragging = false;
  canvasWrap.classList.remove('dragging');
});

// ===== Canvas 点击 =====
canvas.addEventListener('click', e => {
  if (wasDragged) return;
  if (!mapData) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const gx = Math.floor((e.clientX - rect.left) * scaleX / tileSize);
  const gy = Math.floor((e.clientY - rect.top) * scaleY / tileSize);
  if (gx < 0 || gx >= mapData.width || gy < 0 || gy >= mapData.height) return;

  const evt = mapData.events.find(ev => ev.x === gx && ev.y === gy);
  if (evt) {
    showEventDetail(evt);
  } else {
    pushDetail(
      '<div class="info-block"><h3>空格子</h3>' +
      '<div class="info-row"><span class="info-key">坐标</span>' +
      '<span class="info-val">(' + gx + ', ' + gy + ')</span></div>' +
      '<div style="margin-top:8px;color:var(--text2)">该格子没有事件</div></div>');
  }
});

// ===== 地图信息面板 =====
function showMapInfo() {
  if (!mapData) return;
  const dc = document.getElementById('detailContent');
  let html = '<div class="info-block"><h3>地图信息</h3>';
  html += infoRow('名称', mapData.name);
  html += infoRow('ID', mapData.id);
  html += infoRow('尺寸', mapData.width + ' x ' + mapData.height);
  html += infoRow('BGM', mapData.bgm || '无');
  html += infoRow('事件数', mapData.events.length);
  html += '</div>';

  const TYPE_LABEL = {treasure:'宝箱',transfer:'传送',battle:'战斗',dialog:'对话',other:'其他'};
  const TYPE_COLOR = {treasure:'#ffd43b',transfer:'#74b9ff',battle:'#ff6b6b',dialog:'#51cf66',other:'#636e72'};

  if (mapData.events.length > 0) {
    html += '<div class="info-block"><h3>事件列表 (点击查看详情)</h3>';
    mapData.events.forEach(evt => {
      const tc = TYPE_COLOR[evt.type]||TYPE_COLOR.other;
      const tl = TYPE_LABEL[evt.type]||'其他';
      html += '<div class="evt-list-item" onclick="showEventDetail(mapData.events.find(e=>e.id==' + evt.id + '))">';
      html += '<span class="dot" style="background:'+tc+'"></span>';
      html += '<span class="eid">#' + String(evt.id).padStart(3,'0') + '</span>';
      html += '<span class="etype" style="color:'+tc+'">['+tl+']</span>';
      html += '<span class="ename">' + esc(evt.name) + '</span>';
      html += '<span class="epos">(' + evt.x + ',' + evt.y + ')</span>';
      html += '</div>';
    });
    html += '</div>';
  }
  pushDetail(html);
}

function infoRow(key, val) {
  return '<div class="info-row"><span class="info-key">' + key +
    '</span><span class="info-val">' + esc(String(val)) + '</span></div>';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function escAttr(s) {
  return esc(String(s || '')).replace(/"/g, '&quot;');
}

function renderCmdText(cmd) {
  let text = cmd.text || '';
  if (!cmd.refs || !cmd.refs.length) return esc(text);
  let html = esc(text);
  cmd.refs.forEach(ref => {
    if (!ref || !ref.name) return;
    const safeName = esc(ref.name);
    let link = '';
    if (ref.kind === 'troop') {
      const payload = encodeURIComponent(JSON.stringify(ref));
      const badge = ref.special ? '<span class="battle-badge">剧情</span>' : '';
      link = '<span class="ref-link" data-kind="troop" data-ref="' + payload + '">' + safeName + '</span>' + badge;
    } else if (ref.kind === 'encounter') {
      const payload = encodeURIComponent(JSON.stringify(ref));
      const badge = ref.special ? '<span class="battle-badge">剧情</span>' : '';
      link = '<span class="ref-link" data-kind="encounter" data-ref="' + payload + '">' + safeName + '</span>' + badge;
    } else if (ref.kind === 'transfer') {
      link = '<span class="ref-link" data-kind="transfer" data-map="' + ref.mapId +
        '" data-x="' + ref.x + '" data-y="' + ref.y + '">' + safeName + '</span>';
    } else {
      link = '<span class="ref-link" data-kind="' + ref.kind +
        '" data-id="' + ref.id + '">' + safeName + '</span>';
    }
    html = html.replace(safeName, link);
  });
  return html;
}

function bringFloatingWindowToFront(win) {
  if (!win) return;
  floatingWindowZ += 1;
  win.style.zIndex = String(floatingWindowZ);
}

function closeFloatingWindow(win) {
  if (!win) return;
  if (floatingWindowDrag && floatingWindowDrag.win === win) {
    floatingWindowDrag = null;
  }
  win.remove();
}

function closeAllFloatingWindows() {
  if (!floatingWindowLayer) return;
  floatingWindowDrag = null;
  floatingWindowLayer.querySelectorAll('.floating-detail').forEach(el => el.remove());
}

function openFloatingWindow(title, html) {
  if (!floatingWindowLayer) return null;

  const win = document.createElement('div');
  win.className = 'floating-detail';
  const seq = floatingWindowSeq++;
  win.style.left = (80 + (seq % 6) * 24) + 'px';
  win.style.top = (110 + (seq % 6) * 20) + 'px';
  bringFloatingWindowToFront(win);

  const head = document.createElement('div');
  head.className = 'floating-header';
  const titleEl = document.createElement('span');
  titleEl.textContent = title || '详情';
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.textContent = '关闭';
  closeBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    closeFloatingWindow(win);
  });
  head.append(titleEl, closeBtn);

  const body = document.createElement('div');
  body.className = 'floating-body';
  body.innerHTML = html || '';

  head.addEventListener('mousedown', function(e) {
    if (e.button !== 0) return;
    bringFloatingWindowToFront(win);
    const rect = win.getBoundingClientRect();
    floatingWindowDrag = {
      win,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
    };
    win.classList.add('dragging');
    e.preventDefault();
  });

  win.addEventListener('mousedown', function() {
    bringFloatingWindowToFront(win);
  });

  win.append(head, body);
  floatingWindowLayer.appendChild(win);
  return win;
}

window.addEventListener('mousemove', function(e) {
  if (!floatingWindowDrag || !floatingWindowDrag.win) return;
  const win = floatingWindowDrag.win;
  const rect = win.getBoundingClientRect();
  const width = Math.max(220, rect.width);
  const height = Math.max(120, rect.height);
  const left = Math.max(8, Math.min(window.innerWidth - width - 8, e.clientX - floatingWindowDrag.offsetX));
  const top = Math.max(8, Math.min(window.innerHeight - height - 8, e.clientY - floatingWindowDrag.offsetY));
  win.style.left = left + 'px';
  win.style.top = top + 'px';
});

window.addEventListener('mouseup', function() {
  if (!floatingWindowDrag || !floatingWindowDrag.win) return;
  floatingWindowDrag.win.classList.remove('dragging');
  floatingWindowDrag = null;
});

function showInlineRefPanel(title, html) {
  const dc = document.getElementById('detailContent');
  if (!dc) return;
  let panel = dc.querySelector('.inline-ref-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.className = 'info-block inline-ref-panel';
    dc.appendChild(panel);
  }
  panel.innerHTML = '<h3>' + esc(title || '详情') + '</h3>' + (html || '<div style="color:var(--text2)">暂无详情</div>');
  panel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

async function ensureEncData(forceReload) {
  const active = getActiveGameEntry();
  if (!active) throw new Error('当前没有活动游戏，无法加载图鉴');
  const key = buildEncCacheKey(active);
  if (!forceReload && encData && encCacheKey === key) return;
  encData = await apiJson('/api/encyclopedia');
  encCacheKey = key;
}

function findEncItem(kind, id) {
  const list = (encData && encData[kind]) ? encData[kind] : [];
  return list.find(x => x.id === id);
}

function buildItemTipHtml(kind, item) {
  const kindLabel = {items:'物品', weapons:'武器', armors:'防具'}[kind] || kind;
  if (!item) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">' + iconHtml(item.iconIndex) + ' #' + item.id + ' ' + esc(item.name) +
    '<span class="item-tip-kind">[' + kindLabel + ']</span></div>';
  if (item.desc) h += '<div class="item-tip-desc">' + esc(item.desc) + '</div>';

  if (kind === 'weapons') {
    h += '<div class="item-tip-row"><span>类型</span><span class="val">' + esc(item.wtype) + '</span></div>';
  } else if (kind === 'armors') {
    h += '<div class="item-tip-row"><span>防具类型</span><span class="val">' + esc(item.atype) + '</span></div>';
    h += '<div class="item-tip-row"><span>装备位置</span><span class="val">' + esc(item.etype) + '</span></div>';
  } else if (kind === 'items') {
    h += '<div class="item-tip-row"><span>分类</span><span class="val">' + esc(item.itype) + '</span></div>';
    h += '<div class="item-tip-row"><span>范围</span><span class="val">' + esc(item.scope) + '</span></div>';
    h += '<div class="item-tip-row"><span>消耗</span><span class="val">' + (item.consumable ? '是' : '否') + '</span></div>';
  }
  if (item.price !== undefined) {
    h += '<div class="item-tip-row"><span>价格</span><span class="val">' + item.price + 'G</span></div>';
  }

  if (item.params && item.params.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">能力值</div><div class="item-tip-list">';
    item.params.forEach(p => {
      const sign = p.value > 0 ? '+' : '';
      h += '<div>' + esc(p.name) + ' ' + sign + p.value + '</div>';
    });
    h += '</div></div>';
  }

  if (item.traits && item.traits.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">特性</div><div class="item-tip-list">';
    item.traits.forEach(t => { h += '<div>· ' + esc(t) + '</div>'; });
    h += '</div></div>';
  }

  if (item.effects && item.effects.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">使用效果</div><div class="item-tip-list">';
    item.effects.forEach(e => { h += '<div>· ' + esc(e) + '</div>'; });
    h += '</div></div>';
  }
  return h;
}

function buildTroopTipHtml(ref) {
  if (!ref) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">#' + ref.id + ' ' + esc(ref.name) +
    '<span class="item-tip-kind">[敌群]</span>';
  if (ref.special) h += '<span class="item-tip-badge">剧情</span>';
  h += '</div>';
  if (ref.specialReason) h += '<div class="item-tip-desc">' + esc(ref.specialReason) + '</div>';
  h += '<div class="item-tip-row"><span>类型</span><span class="val">' + esc(ref.methodLabel || '战斗') + '</span></div>';
  h += '<div class="item-tip-row"><span>可逃跑</span><span class="val">' + (ref.canEscape ? '是' : '否') + '</span></div>';
  h += '<div class="item-tip-row"><span>可失败</span><span class="val">' + (ref.canLose ? '是' : '否') + '</span></div>';

  if (ref.enemies && ref.enemies.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">敌群成员</div><div class="item-tip-list">';
    ref.enemies.forEach(e => {
      let line = '<span class="ref-link" data-kind="enemies" data-id="' + e.id + '">' + esc(e.name) + '</span> x' + e.count;
      if (e.hidden) line += ' (隐藏' + e.hidden + ')';
      h += '<div>· ' + line + '</div>';
    });
    h += '</div></div>';
  } else {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">敌群成员</div><div class="item-tip-list">';
    h += '<div style="color:var(--text2)">无成员数据</div></div>';
  }
  return h;
}

function buildEncounterTipHtml(ref) {
  if (!ref) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">' + esc(ref.name || '随机遇敌') +
    '<span class="item-tip-kind">[遇敌]</span>';
  if (ref.special) h += '<span class="item-tip-badge">剧情</span>';
  h += '</div>';
  if (ref.specialReason) h += '<div class="item-tip-desc">' + esc(ref.specialReason) + '</div>';
  if (ref.mapName) {
    h += '<div class="item-tip-row"><span>地图</span><span class="val">' + esc(ref.mapName) + (ref.mapId ? ' (#' + ref.mapId + ')' : '') + '</span></div>';
  }
  if (ref.encounterStep !== undefined && ref.encounterStep !== null) {
    h += '<div class="item-tip-row"><span>遇敌步数</span><span class="val">' + ref.encounterStep + '</span></div>';
  }
  if (ref.canEscape !== undefined) {
    h += '<div class="item-tip-row"><span>可逃跑</span><span class="val">' + (ref.canEscape ? '是' : '否') + '</span></div>';
  }
  if (ref.canLose !== undefined) {
    h += '<div class="item-tip-row"><span>可失败</span><span class="val">' + (ref.canLose ? '是' : '否') + '</span></div>';
  }
  const list = ref.encounters || [];
  h += '<div class="item-tip-section"><div class="item-tip-section-title">可能敌群</div><div class="item-tip-list">';
  if (!list.length) {
    h += '<div style="color:var(--text2)">无遇敌列表</div>';
  } else {
    list.forEach(e => {
      const region = (e.regionSet && e.regionSet.length) ? ('区域 ' + e.regionSet.join(',')) : '全部区域';
      const line = '#' + e.troopId + ' ' + esc(e.troopName) + ' (权重:' + (e.weight || 1) + ' / ' + region + ')';
      h += '<div>· ' + line + '</div>';
      if (e.enemies && e.enemies.length) {
        e.enemies.forEach(en => {
          let s = '<span class="ref-link" data-kind="enemies" data-id="' + en.id + '">' + esc(en.name) + '</span> x' + en.count;
          if (en.hidden) s += ' (隐藏' + en.hidden + ')';
          h += '<div style="margin-left:10px;color:var(--text2)">- ' + s + '</div>';
        });
      }
    });
  }
  h += '</div></div>';
  return h;
}

function buildEnemyTipHtml(enemy) {
  if (!enemy) return '<div style="color:var(--text2)">未找到条目</div>';
  let h = '<div class="item-tip-title">' + iconHtml(enemy.iconIndex) + ' #' + enemy.id + ' ' + esc(enemy.name) +
    '<span class="item-tip-kind">[怪物]</span></div>';
  if (enemy.portraitRel) {
    h += '<img class="item-tip-portrait" src="/api/assets/file?rel=' + encodeURIComponent(enemy.portraitRel) + '" alt="' + escAttr(enemy.name) + '">';
  } else {
    h += '<div class="item-tip-portrait-empty">未找到怪物大图</div>';
  }
  h += '<div class="item-tip-row"><span>经验值</span><span class="val">' + enemy.exp + '</span></div>';
  h += '<div class="item-tip-row"><span>金币</span><span class="val">' + enemy.gold + '</span></div>';

  if (enemy.params && enemy.params.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">能力值</div><div class="item-tip-list">';
    enemy.params.forEach(p => {
      const sign = p.value > 0 ? '+' : '';
      h += '<div>' + esc(p.name) + ' ' + sign + p.value + '</div>';
    });
    h += '</div></div>';
  }

  if (enemy.traits && enemy.traits.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">特性</div><div class="item-tip-list">';
    enemy.traits.forEach(t => { h += '<div>· ' + esc(t) + '</div>'; });
    h += '</div></div>';
  }

  if (enemy.drops && enemy.drops.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">掉落物</div><div class="item-tip-list">';
    enemy.drops.forEach(d => { h += '<div>· ' + esc(d) + '</div>'; });
    h += '</div></div>';
  }

  if (enemy.actions && enemy.actions.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">行动模式</div><div class="item-tip-list">';
    enemy.actions.forEach(a => {
      const sid = Number(a.skillId || 0);
      const skillName = sid > 0
        ? '<span class="ref-link" data-kind="skills" data-id="' + sid + '">' + esc(a.skill) + '</span>'
        : esc(a.skill);
      h += '<div>· ' + skillName + ' (优先度:' + a.rating + ')</div>';
    });
    h += '</div></div>';
  }
  return h;
}

function showItemTooltip(kind, item) {
  openFloatingWindow('条目详情', buildItemTipHtml(kind, item));
}

function showTroopTooltip(ref) {
  showInlineRefPanel('敌群详情', buildTroopTipHtml(ref));
}

function showEncounterTooltip(ref) {
  showInlineRefPanel('遇敌详情', buildEncounterTipHtml(ref));
}

function showEnemyTooltip(enemy) {
  openFloatingWindow('怪物详情', buildEnemyTipHtml(enemy));
}

function buildSkillTipHtml(skill) {
  if (!skill) return '<div style="color:var(--text2)">未找到技能</div>';
  let h = '<div class="item-tip-title">' + iconHtml(skill.iconIndex) + ' #' + skill.id + ' ' + esc(skill.name) +
    '<span class="item-tip-kind">[技能]</span></div>';
  if (skill.desc) h += '<div class="item-tip-desc">' + esc(skill.desc) + '</div>';
  h += '<div class="item-tip-row"><span>技能类型</span><span class="val">' + esc(skill.stype || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>作用范围</span><span class="val">' + esc(skill.scope || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>可用场景</span><span class="val">' + esc(skill.occasion || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>命中类型</span><span class="val">' + esc(skill.hitType || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>MP消耗</span><span class="val">' + Number(skill.mpCost || 0) + '</span></div>';
  h += '<div class="item-tip-row"><span>TP消耗</span><span class="val">' + Number(skill.tpCost || 0) + '</span></div>';
  h += '<div class="item-tip-row"><span>成功率</span><span class="val">' + Number(skill.successRate || 0) + '%</span></div>';
  h += '<div class="item-tip-row"><span>重复次数</span><span class="val">' + Number(skill.repeats || 1) + '</span></div>';
  h += '<div class="item-tip-row"><span>速度修正</span><span class="val">' + Number(skill.speed || 0) + '</span></div>';
  h += '<div class="item-tip-row"><span>伤害类型</span><span class="val">' + esc(skill.damageType || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>伤害属性</span><span class="val">' + esc(skill.damageElement || '?') + '</span></div>';
  h += '<div class="item-tip-row"><span>波动</span><span class="val">' + Number(skill.damageVariance || 0) + '%</span></div>';
  h += '<div class="item-tip-row"><span>可暴击</span><span class="val">' + (skill.damageCritical ? '是' : '否') + '</span></div>';
  if (skill.formula) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">计算公式</div>';
    h += '<div class="formula-raw">' + esc(skill.formula) + '</div>';
    if (skill.formulaPretty) h += '<div class="formula-pretty">' + esc(skill.formulaPretty) + '</div>';
    h += '</div>';
  } else if (skill.legacyDamage) {
    const ld = skill.legacyDamage;
    h += '<div class="item-tip-section"><div class="item-tip-section-title">机制（VX旧版）</div>';
    h += '<div>· 基础伤害: ' + Number(ld.baseDamage || 0) + '</div>';
    h += '<div>· 攻击力系数: ' + Number(ld.atkF || 0) + '%</div>';
    h += '<div>· 魔法力系数: ' + Number(ld.spiF || 0) + '%</div>';
    h += '<div>· 波动范围: ' + Number(ld.variance || 0) + '%</div>';
    h += '</div>';
  }
  if (skill.formulaTips && skill.formulaTips.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">说明</div><div class="item-tip-list">';
    skill.formulaTips.forEach(t => { h += '<div>· ' + esc(t) + '</div>'; });
    h += '</div></div>';
  }
  if (skill.effects && skill.effects.length) {
    h += '<div class="item-tip-section"><div class="item-tip-section-title">附加效果</div><div class="item-tip-list">';
    skill.effects.forEach(e => { h += '<div>· ' + esc(e) + '</div>'; });
    h += '</div></div>';
  }
  return h;
}

function showSkillTooltip(skill) {
  openFloatingWindow('技能详情', buildSkillTipHtml(skill));
}

document.addEventListener('click', async e => {
  const link = e.target.closest('.ref-link');
  if (link) {
    e.preventDefault();
    e.stopPropagation();
    const kind = link.dataset.kind;
    if (kind === 'troop') {
      const payload = link.dataset.ref || '';
      let ref = null;
      try { ref = JSON.parse(decodeURIComponent(payload)); } catch (err) { ref = null; }
      showTroopTooltip(ref);
      return;
    }
    if (kind === 'encounter') {
      const payload = link.dataset.ref || '';
      let ref = null;
      try { ref = JSON.parse(decodeURIComponent(payload)); } catch (err) { ref = null; }
      showEncounterTooltip(ref);
      return;
    }
    if (kind === 'transfer') {
      const mapId = parseInt(link.dataset.map || '0', 10);
      const x = parseInt(link.dataset.x || '0', 10);
      const y = parseInt(link.dataset.y || '0', 10);
      if (!mapId) return;
      await loadMap(mapId);
      if (!isNaN(x) && !isNaN(y)) focusMapCell(x, y);
      return;
    }
    if (kind === 'enemies') {
      const id = parseInt(link.dataset.id || '0', 10);
      if (!id) return;
      await ensureAssetMeta(false);
      await ensureEncData();
      const enemy = findEncItem('enemies', id);
      showEnemyTooltip(enemy);
      return;
    }
    if (kind === 'skills') {
      const id = parseInt(link.dataset.id || '0', 10);
      if (!id) return;
      await ensureAssetMeta(false);
      await ensureEncData();
      const skill = findEncItem('skills', id);
      showSkillTooltip(skill);
      return;
    }
    const id = parseInt(link.dataset.id || '0', 10);
    if (!kind || !id) return;
    await ensureAssetMeta(false);
    await ensureEncData();
    const item = findEncItem(kind, id);
    showItemTooltip(kind, item);
    return;
  }
});

// ===== 事件详情 =====
function showEventDetail(evt) {
  const dc = document.getElementById('detailContent');
  let html = '<div class="info-block"><h3>事件详情</h3>';
  html += infoRow('ID', evt.id);
  html += infoRow('名称', evt.name || '(无名)');
  html += infoRow('坐标', '(' + evt.x + ', ' + evt.y + ')');
  html += infoRow('页数', evt.pageCount);
  html += '</div>';

  // 事件页标签
  if (evt.pages.length > 1) {
    html += '<div class="page-tabs">';
    evt.pages.forEach((pg, i) => {
      html += '<div class="page-tab' + (i===0?' active':'') +
        '" onclick="switchPage(this,' + i + ')">' + pg.index + '</div>';
    });
    html += '</div>';
  }

  // 各页内容
  evt.pages.forEach((pg, i) => {
    html += '<div class="page-content" data-page="' + i + '"' +
      (i > 0 ? ' style="display:none"' : '') + '>';
    html += renderPage(pg);
    html += '</div>';
  });

  pushDetail(html);
  const firstPage = document.querySelector('.page-content[data-page="0"]');
  if (firstPage) hydratePageVisuals(firstPage);
}

function switchPage(el, idx) {
  el.parentElement.querySelectorAll('.page-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  let activePage = null;
  document.querySelectorAll('.page-content').forEach(p => {
    p.style.display = p.dataset.page == idx ? '' : 'none';
    if (p.dataset.page == idx) activePage = p;
  });
  if (activePage) hydratePageVisuals(activePage);
}

function toggleFoldSection(headEl) {
  const body = headEl.nextElementSibling;
  if (!body) return;
  body.classList.toggle('collapsed');
  headEl.classList.toggle('collapsed', body.classList.contains('collapsed'));
}

function lockCmdWheel(e, container) {
  container.scrollTop += e.deltaY;
  e.preventDefault();
  e.stopPropagation();
}

function resolveVisualUrl(kind, name) {
  const file = String(name || '').trim();
  if (!file) return '';
  const engine = String((mapData && mapData.engine) || 'mv').toLowerCase();
  if (kind === 'character') {
    if (engine === 'mv') return '/api/assets/file?rel=' + encodeURIComponent('img/characters/' + file + '.png');
    return '/api/assets/file?rel=' + encodeURIComponent('Graphics/Characters/' + file + '.png');
  }
  if (kind === 'face') {
    if (engine === 'mv') return '/api/assets/file?rel=' + encodeURIComponent('img/faces/' + file + '.png');
    return '/api/assets/file?rel=' + encodeURIComponent('Graphics/Faces/' + file + '.png');
  }
  return '';
}

function toInt(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n | 0;
}

function clampInt(value, fallback, min, max) {
  const n = toInt(value, fallback);
  if (n < min) return min;
  if (n > max) return max;
  return n;
}

function loadImageCached(src) {
  if (spriteImageCache.has(src)) return spriteImageCache.get(src);
  const promise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = function() { resolve(img); };
    img.onerror = function() { reject(new Error('image-load-failed')); };
    img.src = src;
  });
  spriteImageCache.set(src, promise);
  return promise;
}

function drawSpriteFrame(ctx2d, img, sx, sy, sw, sh, dw, dh) {
  if (sw <= 0 || sh <= 0) throw new Error('invalid-frame-size');
  ctx2d.clearRect(0, 0, dw, dh);
  ctx2d.imageSmoothingEnabled = false;
  const scale = Math.min(dw / sw, dh / sh);
  const rw = Math.max(1, Math.floor(sw * scale));
  const rh = Math.max(1, Math.floor(sh * scale));
  const dx = Math.floor((dw - rw) / 2);
  const dy = Math.floor((dh - rh) / 2);
  ctx2d.drawImage(img, sx, sy, sw, sh, dx, dy, rw, rh);
}

function drawCharacterPreview(canvas, img, forcedPattern) {
  const isBig = canvas.dataset.isBig === '1';
  const characterIndex = clampInt(canvas.dataset.characterIndex, 0, 0, 7);
  const pattern = clampInt((forcedPattern === undefined ? canvas.dataset.pattern : forcedPattern), 1, 0, 2);
  const direction = clampInt(canvas.dataset.direction, 2, 2, 8);
  const directionRowMap = {2: 0, 4: 1, 6: 2, 8: 3};
  const dirRow = directionRowMap[direction] !== undefined ? directionRowMap[direction] : 0;

  const columns = isBig ? 3 : 12;
  const rows = isBig ? 4 : 8;
  const cellW = Math.floor(img.width / columns);
  const cellH = Math.floor(img.height / rows);
  if (cellW <= 0 || cellH <= 0) throw new Error('invalid-character-sheet');

  const blockX = isBig ? 0 : (characterIndex % 4) * (cellW * 3);
  const blockY = isBig ? 0 : Math.floor(characterIndex / 4) * (cellH * 4);
  const sx = blockX + pattern * cellW;
  const sy = blockY + dirRow * cellH;
  drawSpriteFrame(canvas.getContext('2d'), img, sx, sy, cellW, cellH, canvas.width, canvas.height);
}

function drawFacePreview(canvas, img) {
  const idx = clampInt(canvas.dataset.faceIndex, 0, 0, 7);
  const cols = 4;
  const rows = 2;
  const cellW = Math.floor(img.width / cols);
  const cellH = Math.floor(img.height / rows);
  if (cellW <= 0 || cellH <= 0) throw new Error('invalid-face-sheet');
  const sx = (idx % cols) * cellW;
  const sy = Math.floor(idx / cols) * cellH;
  drawSpriteFrame(canvas.getContext('2d'), img, sx, sy, cellW, cellH, canvas.width, canvas.height);
}

function stopCharacterAnimation(canvas) {
  const timer = characterAnimTimers.get(canvas);
  if (timer) {
    clearInterval(timer);
    characterAnimTimers.delete(canvas);
  }
}

function startCharacterAnimation(canvas, img) {
  stopCharacterAnimation(canvas);
  const seq = [0, 1, 2, 1];
  let idx = 0;
  const timer = setInterval(() => {
    if (!canvas.isConnected) {
      stopCharacterAnimation(canvas);
      return;
    }
    const page = canvas.closest('.page-content');
    if (page && page.style.display === 'none') return;
    try {
      drawCharacterPreview(canvas, img, seq[idx % seq.length]);
    } catch (_e) {
      stopCharacterAnimation(canvas);
      const fallback = canvas.nextElementSibling;
      canvas.style.display = 'none';
      if (fallback) fallback.style.display = '';
      return;
    }
    idx += 1;
  }, 260);
  characterAnimTimers.set(canvas, timer);
}

async function renderVisualCanvas(canvas) {
  if (!canvas || canvas.dataset.rendered === '1') return;
  const src = String(canvas.dataset.src || '').trim();
  const kind = String(canvas.dataset.visualKind || '').trim();
  const fallback = canvas.nextElementSibling;
  canvas.dataset.rendered = '1';
  if (!src || !kind) {
    canvas.style.display = 'none';
    if (fallback) fallback.style.display = '';
    return;
  }
  try {
    const img = await loadImageCached(src);
    if (kind === 'character') {
      drawCharacterPreview(canvas, img);
      startCharacterAnimation(canvas, img);
    } else if (kind === 'face') {
      drawFacePreview(canvas, img);
    } else {
      throw new Error('unsupported-visual-kind');
    }
    canvas.style.display = '';
    if (fallback) fallback.style.display = 'none';
  } catch (e) {
    stopCharacterAnimation(canvas);
    canvas.style.display = 'none';
    if (fallback) fallback.style.display = '';
  }
}

function hydratePageVisuals(root) {
  if (!root) return;
  const list = root.querySelectorAll('canvas[data-visual-kind]');
  list.forEach(c => { renderVisualCanvas(c); });
}

function buildPageVisualHtml(visual) {
  if (!visual || typeof visual !== 'object') return '';
  const charName = String(visual.characterName || '').trim();
  const faceName = String(visual.faceName || '').trim();
  if (!charName && !faceName) return '';

  let h = '<div class="event-visuals">';
  if (charName) {
    const url = resolveVisualUrl('character', charName);
    const characterIndex = clampInt(visual.characterIndex, 0, 0, 7);
    const direction = clampInt(visual.direction, 2, 2, 8);
    const pattern = clampInt(visual.pattern, 1, 0, 2);
    const isBig = !!visual.isBigCharacter;
    h += '<div class="event-visual">';
    h += '<div class="label">角色帧 #' + characterIndex + ' D' + direction + ' P' + pattern + '</div>';
    h += '<canvas class="event-visual-img event-visual-canvas" width="72" height="72" data-visual-kind="character" data-src="' + escAttr(url) + '" data-character-index="' + characterIndex + '" data-direction="' + direction + '" data-pattern="' + pattern + '" data-is-big="' + (isBig ? '1' : '0') + '"></canvas>';
    h += '<div class="event-visual-fallback" style="display:none">角色图加载失败</div>';
    h += '</div>';
  }
  if (faceName) {
    const url = resolveVisualUrl('face', faceName);
    const faceIndex = clampInt(visual.faceIndex, 0, 0, 7);
    h += '<div class="event-visual">';
    h += '<div class="label">脸图 #' + faceIndex + '</div>';
    h += '<canvas class="event-visual-img event-visual-canvas" width="72" height="72" data-visual-kind="face" data-src="' + escAttr(url) + '" data-face-index="' + faceIndex + '"></canvas>';
    h += '<div class="event-visual-fallback" style="display:none">脸图加载失败</div>';
    h += '</div>';
  }
  h += '</div>';
  return h;
}

function renderPage(pg) {
  let h = '<div class="fold-block">';
  h += '<div class="fold-head" onclick="toggleFoldSection(this)"><span class="caret">▼</span><span>事件页 ' + pg.index + ' - 基本信息</span></div>';
  h += '<div class="fold-body">';
  h += infoRow('触发', pg.trigger);
  if (pg.conditions.length > 0) {
    h += '<div style="margin-top:4px;color:var(--orange);font-size:12px">';
    h += '<b>出现条件:</b><br>';
    pg.conditions.forEach(c => { h += '  ' + esc(c) + '<br>'; });
    h += '</div>';
  }
  h += buildPageVisualHtml(pg.visual);
  h += '</div>';
  h += '</div>';

  // 指令列表
  if (pg.commands.length > 0) {
    h += '<div class="fold-block">';
    h += '<div class="fold-head" onclick="toggleFoldSection(this)"><span class="caret">▼</span><span>指令内容</span></div>';
    h += '<div class="fold-body"><div class="cmd-scroll" onwheel="lockCmdWheel(event,this)">';
    pg.commands.forEach(cmd => {
      const pad = cmd.indent * 16;
      if (cmd.cls === 'cmd-common-event') {
        const m = cmd.text.match(/#(\d+)/);
        const ceId = m ? m[1] : '0';
        h += '<div class="cmd-line ' + cmd.cls + '" style="padding-left:' + pad + 'px" onclick="loadCommonEvent(' + ceId + ')">';
      } else {
        h += '<div class="cmd-line ' + (cmd.cls||'') + '" style="padding-left:' + pad + 'px">';
      }
      h += renderCmdText(cmd);
      h += '</div>';
    });
    h += '</div></div></div>';
  }
  return h;
}

// ===== 公共事件详情 =====
async function loadCommonEvent(ceId) {
  const dc = document.getElementById('detailContent');
  dc.innerHTML = '<div class="empty-state"><div>加载公共事件...</div></div>';
  let ce;
  try {
    ce = await apiJson('/api/common_event/' + ceId);
  } catch (e) {
    dc.innerHTML = '<div class="empty-state"><div>' + esc(e.message) + '</div></div>';
    return;
  }
  let html = '<div class="info-block"><h3>公共事件详情</h3>';
  html += infoRow('ID', ce.id);
  html += infoRow('名称', ce.name || '(无名)');
  html += infoRow('触发', ce.trigger);
  if (ce.switchId) html += infoRow('条件开关', ce.switchName + ' (#' + ce.switchId + ')');
  html += '</div>';
  if (ce.commands && ce.commands.length > 0) {
    html += '<div class="fold-block">';
    html += '<div class="fold-head" onclick="toggleFoldSection(this)"><span class="caret">▼</span><span>指令内容</span></div>';
    html += '<div class="fold-body"><div class="cmd-scroll" onwheel="lockCmdWheel(event,this)">';
    ce.commands.forEach(function(cmd) {
      const pad = cmd.indent * 16;
      if (cmd.cls === 'cmd-common-event') {
        const m = cmd.text.match(/#(\d+)/);
        const cid = m ? m[1] : '0';
        html += '<div class="cmd-line ' + cmd.cls + '" style="padding-left:' + pad + 'px" onclick="loadCommonEvent(' + cid + ')">';
      } else {
        html += '<div class="cmd-line ' + (cmd.cls||'') + '" style="padding-left:' + pad + 'px">';
      }
      html += renderCmdText(cmd) + '</div>';
    });
    html += '</div></div></div>';
  }
  pushDetail(html);
}

// ===== 全局搜索 =====
const gsInput = document.getElementById('globalSearchInput');
const gsBtn = document.getElementById('globalSearchBtn');
const gsDefaultPlaceholder = '全图搜索: 物品名 / 对话内容 / 事件指令...';
const gsEncPlaceholder = '图鉴搜索: 当前分类名称...';

function isEncyclopediaOpen() {
  const p = document.getElementById('encPanel');
  return !!p && p.style.display !== 'none';
}

function updateGlobalSearchMode() {
  const inEnc = isEncyclopediaOpen();
  gsBtn.textContent = inEnc ? '筛选图鉴' : '搜索';
  gsInput.placeholder = inEnc ? gsEncPlaceholder : gsDefaultPlaceholder;
  if (inEnc) {
    const encInput = document.getElementById('encSearch');
    gsInput.value = encInput ? (encInput.value || '') : '';
  }
}

async function runMapGlobalSearch(keyword) {
  const kw = String(keyword || '').trim();
  if (!kw) return;
  const dc = document.getElementById('detailContent');
  dc.innerHTML = '<div class="empty-state"><div>搜索中，请稍候...</div></div>';
  setStatus('正在搜索: ' + kw);
  try {
    const data = await apiJson('/api/search?q=' + encodeURIComponent(kw));
    setStatus('搜索完成 — 找到 ' + data.length + ' 个结果');
    renderSearchResults(data, kw);
  } catch (e) {
    setStatus('搜索失败: ' + e.message);
    dc.innerHTML = '<div class="empty-state"><div>' + esc(e.message) + '</div></div>';
  }
}

function runEncSearch(keyword) {
  const kw = String(keyword || '');
  const encInput = document.getElementById('encSearch');
  if (encInput) encInput.value = kw;
  renderEncList();
  setStatus(kw.trim() ? ('图鉴筛选[' + encTab + ']: ' + kw.trim()) : ('图鉴筛选[' + encTab + '] 已清空'));
}

async function globalSearch() {
  const kw = gsInput.value.trim();
  if (isEncyclopediaOpen()) {
    runEncSearch(kw);
    return;
  }
  await runMapGlobalSearch(kw);
}

function renderSearchResults(data, kw) {
  const dc = document.getElementById('detailContent');
  if (data.length === 0) {
    pushDetail('<div class="empty-state"><div>未找到匹配结果</div></div>');
    return;
  }
  const TC = {treasure:'#ffd43b',transfer:'#74b9ff',battle:'#ff6b6b',dialog:'#51cf66',other:'#636e72'};
  const TL = {treasure:'宝箱',transfer:'传送',battle:'战斗',dialog:'对话',other:'其他'};
  let html = '<div class="info-block"><h3>搜索结果: "' + esc(kw) + '" (' + data.length + ' 条)</h3></div>';
  data.forEach((r, i) => {
    const tc = TC[r.type] || TC.other;
    const tl = TL[r.type] || '其他';
    html += '<div class="search-result" onclick="gotoResult('+i+')">';
    html += '<div class="sr-header">';
    html += '<span class="dot" style="background:'+tc+'"></span>';
    html += '<span class="sr-map">' + esc(r.mapName) + '</span>';
    html += '<span class="sr-evt">' + esc(r.eventName||'(无名)') + ' <span style="color:'+tc+'">['+tl+']</span></span>';
    html += '<span class="sr-pos">(' + r.x + ',' + r.y + ')</span>';
    html += '</div>';
    html += '<div class="sr-match">';
    r.matches.forEach(m => { html += esc(m) + '<br>'; });
    html += '</div></div>';
  });
  pushDetail(html);
  window._searchResults = data;
}

async function gotoResult(idx) {
  const r = window._searchResults[idx];
  if (!r) return;
  await loadMap(r.mapId);
  const evt = mapData.events.find(e => e.id === r.eventId);
  if (evt) showEventDetail(evt);
}

gsBtn.addEventListener('click', globalSearch);
gsInput.addEventListener('keydown', e => { if (e.key === 'Enter') globalSearch(); });

// ===== 图鉴 =====
let encTab = 'weapons';
let encSelIdx = -1;

function toggleEncyclopedia() {
  const p = document.getElementById('encPanel');
  const m = document.querySelector('.main');
  if (p.style.display === 'none') {
    p.style.display = 'flex';
    m.style.display = 'none';
    const encInput = document.getElementById('encSearch');
    if (encInput) encInput.value = gsInput.value.trim();
    updateGlobalSearchMode();
    if (!encData) loadEncyclopedia(false);
    else renderEncList();
  } else {
    p.style.display = 'none';
    m.style.display = 'flex';
    gsInput.value = '';
    updateGlobalSearchMode();
  }
}

function switchEncTab(tab) {
  encTab = tab;
  encSelIdx = -1;
  document.querySelectorAll('.enc-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.getElementById('encDetail').innerHTML = '<div style="color:var(--muted)">点击左侧条目查看详情</div>';
  renderEncList();
}

async function loadEncyclopedia(forceReload) {
  document.getElementById('encList').innerHTML = '<div style="padding:20px;color:var(--muted)">加载中...</div>';
  try {
    await ensureAssetMeta(false);
    await ensureEncData(!!forceReload);
    renderEncList();
    if (encSelIdx >= 0) showEncDetail(encSelIdx);
  } catch (e) {
    document.getElementById('encList').innerHTML = '<div style="padding:20px;color:var(--muted)">' + esc(e.message) + '</div>';
  }
}

function filterEnc() {
  if (isEncyclopediaOpen()) {
    const encInput = document.getElementById('encSearch');
    gsInput.value = encInput ? (encInput.value || '') : '';
  }
  renderEncList();
}

function renderEncList() {
  if (!encData) return;
  const list = encData[encTab] || [];
  const q = document.getElementById('encSearch').value.toLowerCase();
  const filtered = q ? list.filter(x => x.name.toLowerCase().includes(q)) : list;
  const el = document.getElementById('encList');
  let html = '';
  filtered.forEach((item, i) => {
    const origIdx = list.indexOf(item);
    let right = '';
    if (encTab === 'enemies') {
      right = item.exp ? `<span class="price">EXP:${item.exp} G:${item.gold}</span>` : '';
    } else if (encTab === 'skills') {
      const mp = Number(item.mpCost || 0);
      const tp = Number(item.tpCost || 0);
      if (mp > 0 || tp > 0) {
        const parts = [];
        if (mp > 0) parts.push(`MP:${mp}`);
        if (tp > 0) parts.push(`TP:${tp}`);
        right = `<span class="price">${parts.join(' / ')}</span>`;
      } else {
        right = `<span class="price">消耗:0</span>`;
      }
    } else {
      right = item.price ? `<span class="price">${item.price}G</span>` : '';
    }
    html += `<div class="enc-item${origIdx===encSelIdx?' sel':''}" onclick="showEncDetail(${origIdx})">`;
    html += `<span class="enc-item-main">${iconHtml(item.iconIndex)}<span class="name"><span class="eid">#${item.id}</span> ${esc(item.name)}</span></span>${right}</div>`;
  });
  el.innerHTML = html || '<div style="padding:20px;color:var(--muted)">无结果</div>';
}

function showEncDetail(idx) {
  encSelIdx = idx;
  renderEncList();
  const item = (encData[encTab] || [])[idx];
  if (!item) return;
  const el = document.getElementById('encDetail');
  let h = `<div class="enc-detail"><h3>${iconHtml(item.iconIndex)} #${item.id} ${esc(item.name)}</h3>`;

  // 描述
  if (item.desc) h += `<div class="desc">${esc(item.desc)}</div>`;
  if (encTab === 'enemies') {
    if (item.portraitRel) {
      h += `<img class="item-tip-portrait" src="/api/assets/file?rel=${encodeURIComponent(item.portraitRel)}" alt="${escAttr(item.name)}">`;
    } else {
      h += `<div class="item-tip-portrait-empty">未找到怪物大图</div>`;
    }
  }

  // 类型/价格行
  if (encTab === 'weapons') {
    h += `<div class="stat"><span>类型</span><span class="val">${esc(item.wtype)}</span></div>`;
  } else if (encTab === 'armors') {
    h += `<div class="stat"><span>防具类型</span><span class="val">${esc(item.atype)}</span></div>`;
    h += `<div class="stat"><span>装备位置</span><span class="val">${esc(item.etype)}</span></div>`;
  } else if (encTab === 'items') {
    h += `<div class="stat"><span>分类</span><span class="val">${esc(item.itype)}</span></div>`;
    h += `<div class="stat"><span>范围</span><span class="val">${esc(item.scope)}</span></div>`;
    h += `<div class="stat"><span>消耗</span><span class="val">${item.consumable ? '是' : '否'}</span></div>`;
  } else if (encTab === 'skills') {
    h += `<div class="stat"><span>技能类型</span><span class="val">${esc(item.stype || '?')}</span></div>`;
    h += `<div class="stat"><span>作用范围</span><span class="val">${esc(item.scope || '?')}</span></div>`;
    h += `<div class="stat"><span>可用场景</span><span class="val">${esc(item.occasion || '?')}</span></div>`;
    h += `<div class="stat"><span>命中类型</span><span class="val">${esc(item.hitType || '?')}</span></div>`;
    h += `<div class="stat"><span>MP消耗</span><span class="val">${Number(item.mpCost || 0)}</span></div>`;
    h += `<div class="stat"><span>TP消耗</span><span class="val">${Number(item.tpCost || 0)}</span></div>`;
    h += `<div class="stat"><span>成功率</span><span class="val">${Number(item.successRate || 0)}%</span></div>`;
    h += `<div class="stat"><span>重复次数</span><span class="val">${Number(item.repeats || 1)}</span></div>`;
    h += `<div class="stat"><span>速度修正</span><span class="val">${Number(item.speed || 0)}</span></div>`;
    h += `<div class="stat"><span>伤害类型</span><span class="val">${esc(item.damageType || '?')}</span></div>`;
    h += `<div class="stat"><span>伤害属性</span><span class="val">${esc(item.damageElement || '?')}</span></div>`;
    h += `<div class="stat"><span>波动</span><span class="val">${Number(item.damageVariance || 0)}%</span></div>`;
    h += `<div class="stat"><span>可暴击</span><span class="val">${item.damageCritical ? '是' : '否'}</span></div>`;
  } else if (encTab === 'enemies') {
    h += `<div class="stat"><span>经验值</span><span class="val">${item.exp}</span></div>`;
    h += `<div class="stat"><span>金币</span><span class="val">${item.gold}</span></div>`;
  }
  if (item.price !== undefined && encTab !== 'enemies') {
    h += `<div class="stat"><span>价格</span><span class="val">${item.price}G</span></div>`;
  }

  // 能力值
  if (item.params && item.params.length) {
    h += `<div class="section"><div class="section-title">能力值</div>`;
    item.params.forEach(p => {
      const color = p.value > 0 ? '#51cf66' : '#ff6b6b';
      h += `<div class="stat"><span>${esc(p.name)}</span><span class="val" style="color:${color}">${p.value > 0 ? '+' : ''}${p.value}</span></div>`;
    });
    h += `</div>`;
  }

  // 特性
  if (item.traits && item.traits.length) {
    h += `<div class="section"><div class="section-title">特性</div>`;
    item.traits.forEach(t => { h += `<div class="trait">· ${esc(t)}</div>`; });
    h += `</div>`;
  }

  // 物品效果
  if (item.effects && item.effects.length) {
    h += `<div class="section"><div class="section-title">使用效果</div>`;
    item.effects.forEach(e => { h += `<div class="trait">· ${esc(e)}</div>`; });
    h += `</div>`;
  }

  // 技能公式与机制说明
  if (encTab === 'skills') {
    if (item.formula) {
      h += `<div class="section"><div class="section-title">计算公式</div>`;
      h += `<div class="formula-raw">${esc(item.formula)}</div>`;
      if (item.formulaPretty) {
        h += `<div class="formula-pretty">${esc(item.formulaPretty)}</div>`;
      }
      h += `</div>`;
    } else if (item.legacyDamage) {
      const ld = item.legacyDamage;
      h += `<div class="section"><div class="section-title">机制（VX旧版）</div>`;
      h += `<div class="trait">· 基础伤害: ${Number(ld.baseDamage || 0)}</div>`;
      h += `<div class="trait">· 攻击力系数: ${Number(ld.atkF || 0)}%</div>`;
      h += `<div class="trait">· 魔法力系数: ${Number(ld.spiF || 0)}%</div>`;
      h += `<div class="trait">· 波动范围: ${Number(ld.variance || 0)}%</div>`;
      h += `</div>`;
    }
    if (item.formulaTips && item.formulaTips.length) {
      h += `<div class="section"><div class="section-title">说明</div>`;
      item.formulaTips.forEach(t => { h += `<div class="trait">· ${esc(t)}</div>`; });
      h += `</div>`;
    }
  }

  // 怪物掉落
  if (item.drops && item.drops.length) {
    h += `<div class="section"><div class="section-title">掉落物</div>`;
    item.drops.forEach(d => { h += `<div class="trait">· ${esc(d)}</div>`; });
    h += `</div>`;
  }

  // 怪物行动
  if (item.actions && item.actions.length) {
    h += `<div class="section"><div class="section-title">行动模式</div>`;
    item.actions.forEach(a => {
      const sid = Number(a.skillId || 0);
      const skillName = sid > 0
        ? `<span class="ref-link" data-kind="skills" data-id="${sid}">${esc(a.skill)}</span>`
        : esc(a.skill);
      h += `<div class="trait">· ${skillName} (优先度:${a.rating})</div>`;
    });
    h += `</div>`;
  }

  h += `</div>`;
  el.innerHTML = h;
}

async function refreshEncyclopediaNow() {
  try {
    invalidateEncyclopediaCache();
    await loadEncyclopedia(true);
    setStatus('图鉴已刷新');
  } catch (e) {
    setStatus('图鉴刷新失败: ' + e.message);
  }
}

// ===== 初始化 =====
gameSelect.addEventListener('change', function() {
  const nextId = this.value || '';
  if (nextId && nextId !== activeGameId) {
    selectGame(nextId);
  }
});

document.getElementById('manageGamesBtn').addEventListener('click', openGameManager);
document.getElementById('closeGameModalBtn').addEventListener('click', closeGameManager);
document.getElementById('registerExeBtn').addEventListener('click', uiRegisterExePath);
document.getElementById('pickExeBtn').addEventListener('click', uiPickExeByDialog);
document.getElementById('encRefreshBtn').addEventListener('click', refreshEncyclopediaNow);
document.getElementById('registerExeInput').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') uiRegisterExePath();
});

gameModal.addEventListener('click', function(e) {
  if (e.target === gameModal) closeGameManager();
});

updateGlobalSearchMode();
loadGames(true);
