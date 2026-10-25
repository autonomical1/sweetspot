import { useEffect, useState } from 'react';
import { ApiError, type Room } from '../../api/client';
import { extraApi, type Product, type ProductsResult } from '../../api/extra';
import { formatFtIn } from '../../lib/format';
import { money, RoleChip, section } from './shared';

function ProductCard({ item }: { item: Product }) {
  return <article className="product-card">{item.thumbnail && <img src={item.thumbnail} alt="" />}<div><div className="product-heading"><RoleChip role={item.role} /><b>{item.title}</b>{item.source === 'stub' && <span className="sample-badge">sample data</span>}</div><span className="product-price">{money(item.price, item.currency)}{item.pair_with ? ' · pair' : ''}</span>{item.seller && <small>{item.seller} · {item.source}</small>}
    {item.specs && <p className="specs">{Object.entries(item.specs).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ')}</p>}
    {item.dimensions && <p className="specs">{formatFtIn(item.dimensions.width)} × {formatFtIn(item.dimensions.height)} × {formatFtIn(item.dimensions.depth)}</p>}
    <a href={item.link} target="_blank" rel="noopener">View</a>
    {(item.alternatives?.length ?? 0) > 0 && <details><summary>Alternatives</summary>{item.alternatives!.map(option => <div className="alternative" key={option.link}>{option.title} · {money(option.price)} <span>{option.price_delta >= 0 ? '+' : ''}{money(option.price_delta)}</span></div>)}</details>}
  </div></article>;
}

export function ShopPanel({ room, hasLayout }: { room: Room | null; hasLayout: boolean }) {
  const [budget, setBudget] = useState(room?.budget ?? 1500); const [result, setResult] = useState<ProductsResult | null>(null); const [error, setError] = useState<ApiError | null>(null); const [loading, setLoading] = useState(false); const [seconds, setSeconds] = useState(0);
  useEffect(() => { if (room) setBudget(room.budget); }, [room?.room_id]);
  useEffect(() => { if (!seconds) return; const timer = window.setInterval(() => setSeconds(value => Math.max(0, value - 1)), 1000); return () => clearInterval(timer); }, [seconds]);
  const load = async () => { if (!room) return; setLoading(true); setError(null); try { setResult(await extraApi.getProducts(room.room_id, budget)); } catch (cause) { const apiError = cause instanceof ApiError ? cause : new ApiError('Could not get products', 0, 'NETWORK'); setError(apiError); setSeconds(apiError.retryAfter ?? 0); } finally { setLoading(false); } };
  if (!room) return <div className="panel-empty">Load a room to build a shopping list.</div>;
  const visible = result?.items.filter(item => !item.included_in && (!item.pair_with || item.role < item.pair_with)) ?? [];
  return <div className="panel-content"><div className="budget-form"><label>Budget <input aria-label="Budget" type="number" min="0" value={budget} onChange={event => setBudget(Number(event.target.value))} /></label><button className="panel-button" onClick={() => void load()} disabled={loading || !hasLayout}>{loading ? 'Finding products…' : 'Get products'}</button></div>
    {!hasLayout && <div className="panel-banner">Place the speakers first.</div>}
    {error && <div className="panel-error">{error.status === 404 ? 'Place the speakers first' : error.status === 429 ? `Waiting on Gemini, retry in ${seconds || error.retryAfter || 0} s` : error.message}<button onClick={() => void load()}>Retry</button></div>}
    {result && <>{section('Recommended equipment', visible.length ? <div>{visible.map(item => <ProductCard key={`${item.role}-${item.link}`} item={item} />)}</div> : <p className="muted">No products matched this budget.</p>)}{result.warnings?.length ? <ul className="panel-list">{result.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul> : null}<div className="budget-total"><div><b>{money(result.total)}</b> of {money(result.budget)}</div><i><span style={{ width: `${Math.min(100, result.total / result.budget * 100)}%` }} /></i><small>Prices from Google Shopping via SerpApi</small></div></>}
  </div>;
}
