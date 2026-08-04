import { ArrowDown, ArrowUp, Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ConfirmModal } from "../components/ConfirmModal";
import { EmptyState, Feedback, LoadingState } from "../components/Feedback";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

const troopLabels: Record<string, string> = {
  dragon: "Rồng điện",
  balloon: "Bóng",
  valkyrie: "Valkyrie",
  hero: "Tướng",
  rage: "Nộ",
  freeze: "Băng",
  poison: "Độc",
};
const spellKinds = new Set(["rage", "freeze", "poison"]);

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function cleanName(value: string): string { return value.trim().replace(/\s+/g, " "); }
function cleanKind(value: string): string {
  return value.trim().toLowerCase().replace(/đ/g, "d").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}
function deployFromCombo(combo: any, fallbackDeploy: any) { return combo?.deploy ?? combo ?? fallbackDeploy ?? {}; }
function comboDeployCopy(deploy: any) {
  const next = clone(deploy ?? {});
  delete next.deploy_zones;
  delete next.spell_groups;
  return next;
}
function remapDeployKind(deploy: any, oldKind: string, newKind: string) {
  const next = clone(deploy ?? {});
  next.sequence = (next.sequence ?? []).map((step: any) => step?.slot === oldKind ? { ...step, slot: newKind } : step);
  next.spell_groups = (next.spell_groups ?? []).map((group: any) => ({ ...group, slots: (group.slots ?? []).map((slot: string) => slot === oldKind ? newKind : slot) }));
  return next;
}
function removeDeployKind(deploy: any, kind: string) {
  const next = clone(deploy ?? {});
  next.sequence = (next.sequence ?? []).filter((step: any) => step?.slot !== kind);
  next.spell_groups = (next.spell_groups ?? []).map((group: any) => ({ ...group, slots: (group.slots ?? []).filter((slot: string) => slot !== kind) }));
  return next;
}

type PendingDelete = { type: "combo" | "troop"; value: string } | null;

export function ComboPage() {
  const { config, loading, saving, error, savedMessage, isDirty, updatePath, save } = useConfigEditor();
  const comboNames = useMemo(() => Object.keys(config?.combos ?? {}), [config]);
  const runningCombo = config?.farm?.combo ?? "";
  const [selectedCombo, setSelectedCombo] = useState("");
  const currentCombo = selectedCombo || runningCombo || comboNames[0] || "";
  const [newComboName, setNewComboName] = useState("");
  const [comboNameDraft, setComboNameDraft] = useState("");
  const [newKindName, setNewKindName] = useState("");
  const [editingKind, setEditingKind] = useState("");
  const [kindNameDraft, setKindNameDraft] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);

  useEffect(() => setComboNameDraft(currentCombo), [currentCombo]);
  if (loading) return <LoadingState label="Đang tải danh sách combo..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const appConfig = config;
  const deploy = deployFromCombo(appConfig.combos?.[currentCombo], appConfig.deploy);
  const sequence = Array.isArray(deploy.sequence) ? deploy.sequence : [];
  const allKinds: string[] = appConfig.slot_detection?.kinds ?? [];
  const troopKinds = allKinds.filter((kind) => !spellKinds.has(kind));
  const troopOptions = troopKinds.map((kind) => ({ label: troopLabels[kind] ?? kind, value: kind }));
  const usedByCombos = (kind: string) => comboNames.filter((name) => (deployFromCombo(appConfig.combos[name], appConfig.deploy).sequence ?? []).some((step: any) => step.slot === kind));

  function updateCombos(next: Record<string, any>) { setNotice(""); updatePath(["combos"], next); }
  function updateDeploy(nextDeploy: any) {
    if (!currentCombo) return;
    const nextCombos = clone(appConfig.combos ?? {});
    nextCombos[currentCombo] = { ...(nextCombos[currentCombo] ?? {}), deploy: nextDeploy };
    updateCombos(nextCombos);
  }
  function setRunningCombo(name: string) { setSelectedCombo(name); updatePath(["farm", "combo"], name); }

  function createCombo() {
    const name = cleanName(newComboName);
    if (!name || appConfig.combos?.[name]) return;
    const next = clone(appConfig.combos ?? {});
    next[name] = { deploy: comboDeployCopy(appConfig.deploy ?? deploy) };
    updateCombos(next);
    setSelectedCombo(name);
    setNewComboName("");
  }

  function renameCombo() {
    const name = cleanName(comboNameDraft);
    if (!currentCombo || !name || name === currentCombo) return;
    if (appConfig.combos?.[name]) { setNotice("Tên combo đã tồn tại."); return; }
    const next = clone(appConfig.combos ?? {});
    next[name] = next[currentCombo];
    delete next[currentCombo];
    updateCombos(next);
    if (runningCombo === currentCombo) updatePath(["farm", "combo"], name);
    setSelectedCombo(name);
  }

  function copyCombo() {
    if (!currentCombo) return;
    let copyName = `${currentCombo} Copy`;
    let index = 2;
    while (appConfig.combos?.[copyName]) { copyName = `${currentCombo} Copy ${index}`; index += 1; }
    const next = clone(appConfig.combos ?? {});
    next[copyName] = { ...clone(next[currentCombo]), deploy: comboDeployCopy(deployFromCombo(next[currentCombo], appConfig.deploy)) };
    updateCombos(next);
    setSelectedCombo(copyName);
  }

  function deleteCombo(name: string) {
    if (!name || comboNames.length <= 1) return;
    const next = clone(appConfig.combos ?? {});
    delete next[name];
    const fallback = Object.keys(next)[0] ?? "";
    updateCombos(next);
    if (runningCombo === name) updatePath(["farm", "combo"], fallback);
    setSelectedCombo(fallback);
  }

  function createTroopKind() {
    const kind = cleanKind(newKindName);
    if (!kind || allKinds.includes(kind)) return;
    updatePath(["slot_detection", "kinds"], [...allKinds, kind]);
    updatePath(["slot_detection", "count_max_by_kind", kind], 99);
    updatePath(["manual_army", "counts", kind], 0);
    setNewKindName("");
  }

  function renameTroopKind(oldKind: string) {
    const nextKind = cleanKind(kindNameDraft);
    if (!nextKind || nextKind === oldKind) { setEditingKind(""); return; }
    if (allKinds.includes(nextKind)) { setNotice("Tên lính đã tồn tại."); return; }
    const maxByKind = clone(appConfig.slot_detection?.count_max_by_kind ?? {});
    maxByKind[nextKind] = maxByKind[oldKind] ?? 99; delete maxByKind[oldKind];
    const manualCounts = clone(appConfig.manual_army?.counts ?? {});
    manualCounts[nextKind] = manualCounts[oldKind] ?? 0; delete manualCounts[oldKind];
    const coordsSlots = clone(appConfig.coords?.slots ?? {});
    if (coordsSlots[oldKind]) { coordsSlots[nextKind] = coordsSlots[oldKind]; delete coordsSlots[oldKind]; }
    const nextCombos = clone(appConfig.combos ?? {});
    for (const name of Object.keys(nextCombos)) nextCombos[name] = { ...(nextCombos[name] ?? {}), deploy: remapDeployKind(deployFromCombo(nextCombos[name], appConfig.deploy), oldKind, nextKind) };
    updatePath(["slot_detection", "kinds"], allKinds.map((kind) => kind === oldKind ? nextKind : kind));
    updatePath(["slot_detection", "count_max_by_kind"], maxByKind);
    updatePath(["manual_army", "counts"], manualCounts);
    updatePath(["coords", "slots"], coordsSlots);
    updatePath(["deploy"], remapDeployKind(appConfig.deploy, oldKind, nextKind));
    updateCombos(nextCombos);
    setEditingKind(""); setKindNameDraft("");
  }

  function deleteTroopKind(kind: string) {
    const maxByKind = clone(appConfig.slot_detection?.count_max_by_kind ?? {});
    const manualCounts = clone(appConfig.manual_army?.counts ?? {});
    const coordsSlots = clone(appConfig.coords?.slots ?? {});
    delete maxByKind[kind]; delete manualCounts[kind]; delete coordsSlots[kind];
    const nextCombos = clone(appConfig.combos ?? {});
    for (const name of Object.keys(nextCombos)) nextCombos[name] = { ...(nextCombos[name] ?? {}), deploy: removeDeployKind(deployFromCombo(nextCombos[name], appConfig.deploy), kind) };
    updatePath(["slot_detection", "kinds"], allKinds.filter((item) => item !== kind));
    updatePath(["slot_detection", "count_max_by_kind"], maxByKind);
    updatePath(["manual_army", "counts"], manualCounts);
    updatePath(["coords", "slots"], coordsSlots);
    updatePath(["deploy"], removeDeployKind(appConfig.deploy, kind));
    updateCombos(nextCombos);
    setNotice(`Đã xóa lính ${troopLabels[kind] ?? kind} khỏi cấu hình.`);
  }

  function updateStep(index: number, key: string, value: unknown) {
    const next = clone(sequence); next[index] = { ...next[index], [key]: value }; updateDeploy({ ...deploy, sequence: next });
  }
  function addStep() { updateDeploy({ ...deploy, sequence: [...sequence, { slot: troopKinds[0] ?? "dragon", count: "all", max_taps: 10, delay: 0.08 }] }); }
  function removeStep(index: number) { updateDeploy({ ...deploy, sequence: sequence.filter((_: unknown, i: number) => i !== index) }); }
  function moveStep(index: number, offset: number) {
    const target = index + offset;
    if (target < 0 || target >= sequence.length) return;
    const next = clone(sequence); [next[index], next[target]] = [next[target], next[index]]; updateDeploy({ ...deploy, sequence: next });
  }

  const deleteDescription = pendingDelete?.type === "combo"
    ? `Combo “${pendingDelete.value}” và sequence của combo sẽ bị xóa. Vùng thả dùng chung không bị ảnh hưởng.`
    : pendingDelete
      ? `Lính “${troopLabels[pendingDelete.value] ?? pendingDelete.value}” sẽ bị xóa khỏi ${usedByCombos(pendingDelete.value).length} combo đang tham chiếu và khỏi cấu hình nhận diện.`
      : "";
  const sharedSpellSlots = (appConfig.deploy?.spell_groups ?? [])
    .filter((group: any) => group.enabled !== false)
    .flatMap((group: any) => (group.slots ?? []).map(String));
  const manualKinds = Array.from(new Set<string>([
    ...sequence.map((step: any) => String(step.slot ?? "")).filter(Boolean),
    "hero",
    ...sharedSpellSlots,
  ]));
  const sequenceKinds = new Set(sequence.map((step: any) => String(step.slot ?? "")).filter(Boolean));
  const supplementalManualKinds = manualKinds.filter((kind) => !sequenceKinds.has(kind));
  const manualArmy = appConfig.manual_army ?? { enabled: false, counts: {} };

  return (
    <div>
      <PageHeader
        eyebrow="Đội hình"
        title="Combo"
        subtitle="Quản lý đội hình, thứ tự thả và cách lấy số lượng quân."
        action={(
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={!currentCombo || currentCombo === runningCombo} onClick={() => setRunningCombo(currentCombo)}>Dùng combo</Button>
            <Button variant="success" loading={saving} disabled={!isDirty} onClick={save}>Lưu cấu hình</Button>
          </div>
        )}
      />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : notice ? <Feedback tone="info" className="mb-5">{notice}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card title="Danh sách combo" subtitle={`${comboNames.length} combo`}>
            <div className="space-y-2">
              {comboNames.map((name) => (
                <button key={name} type="button" onClick={() => setSelectedCombo(name)} className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-3 text-left text-sm transition ${currentCombo === name ? "border-sky-400 bg-sky-400/10 text-white" : "border-white/10 bg-ink-900 text-slate-300 hover:border-white/20"}`}>
                  <span className="min-w-0 truncate font-semibold">{name}</span>
                  {runningCombo === name ? <span className="shrink-0 rounded-full bg-limewash/15 px-2 py-0.5 text-[10px] font-bold text-lime-300">Đang dùng</span> : null}
                </button>
              ))}
            </div>
            <div className="mt-4 border-t border-white/10 pt-4">
              <TextInput label="Tên combo mới" value={newComboName} onChange={(event) => setNewComboName(event.target.value)} />
              <Button className="mt-3 w-full" variant="primary" disabled={!cleanName(newComboName) || Boolean(appConfig.combos?.[cleanName(newComboName)])} onClick={createCombo}><Plus className="h-4 w-4" />Tạo combo</Button>
            </div>
          </Card>

          <details className="rounded-lg border border-white/10 bg-ink-850/90 p-5">
            <summary className="cursor-pointer text-sm font-semibold text-white">Quản lý loại lính</summary>
            <div className="mt-5 space-y-4 border-t border-white/10 pt-5">
              <div>
                <TextInput label="Tên lính mới" value={newKindName} onChange={(event) => setNewKindName(event.target.value)} />
                <Button className="mt-3 w-full" variant="primary" disabled={!cleanKind(newKindName) || allKinds.includes(cleanKind(newKindName))} onClick={createTroopKind}><Plus className="h-4 w-4" />Thêm lính</Button>
              </div>
              <div className="max-h-[380px] space-y-2 overflow-auto pr-1">
                {troopKinds.map((kind) => editingKind === kind ? (
                  <div key={kind} className="rounded-lg border border-sky-400/30 bg-black/20 p-3">
                    <TextInput label="Tên mới" hint="Tên sẽ được cập nhật trong mọi combo và cấu hình liên quan." value={kindNameDraft} onChange={(event) => setKindNameDraft(event.target.value)} />
                    <div className="mt-3 grid grid-cols-2 gap-2"><Button variant="success" onClick={() => renameTroopKind(kind)}>Lưu</Button><Button onClick={() => setEditingKind("")}>Hủy</Button></div>
                  </div>
                ) : (
                  <div key={kind} className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 p-2 pl-3">
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{troopLabels[kind] ?? kind}</span>
                    <Button size="sm" variant="ghost" aria-label={`Sửa ${kind}`} onClick={() => { setEditingKind(kind); setKindNameDraft(kind); }}><Pencil className="h-4 w-4" /></Button>
                    <Button size="sm" variant="ghost" aria-label={`Xóa ${kind}`} onClick={() => setPendingDelete({ type: "troop", value: kind })}><Trash2 className="h-4 w-4 text-rose-300" /></Button>
                  </div>
                ))}
              </div>
            </div>
          </details>
        </div>

        <div className="min-w-0 space-y-5">
          <Card
            title={currentCombo || "Chưa chọn combo"}
            subtitle={currentCombo === runningCombo ? "Combo đang được dùng khi chạy bot" : "Đang chỉnh, chưa đặt làm combo chạy"}
            action={<div className="flex flex-wrap gap-2"><Button size="sm" onClick={copyCombo}><Copy className="h-4 w-4" />Copy</Button><Button size="sm" variant="danger" disabled={comboNames.length <= 1} onClick={() => setPendingDelete({ type: "combo", value: currentCombo })}><Trash2 className="h-4 w-4" />Xóa</Button></div>}
          >
            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <TextInput label="Tên combo" value={comboNameDraft} onChange={(event) => setComboNameDraft(event.target.value)} />
              <Button variant="muted" disabled={!cleanName(comboNameDraft) || comboNameDraft === currentCombo} onClick={renameCombo}>Đổi tên</Button>
            </div>
            <div className="mt-4 border-t border-white/10 pt-4">
              <Toggle label="Tự áp dụng combo khi bắt đầu" checked={Boolean(appConfig.game?.change_combo_on_start)} onChange={(value) => updatePath(["game", "change_combo_on_start"], value)} />
            </div>
          </Card>

          <Card title="Quân trong combo">
            <div className="mb-5">
              <SegmentedControl
                value={manualArmy.enabled ? "manual" : "auto"}
                columns={2}
                options={[
                  { value: "auto", label: "Tự nhận diện" },
                  { value: "manual", label: "Nhập thủ công" },
                ]}
                onChange={(value) => {
                  updatePath(["manual_army", "enabled"], value === "manual");
                  updatePath(["slot_detection", "enabled"], true);
                }}
              />
              {manualArmy.enabled ? (
                <p className="mt-3 text-xs text-slate-400">Số quân mới có hiệu lực từ lần Start tiếp theo.</p>
              ) : null}
            </div>
            {sequence.length ? (
              <div className="overflow-x-auto rounded-lg border border-white/10">
                <table className={`w-full ${manualArmy.enabled ? "min-w-[900px]" : "min-w-[760px]"} table-fixed text-left text-sm`}>
                  <thead className="bg-black/30 text-xs uppercase tracking-wide text-slate-500">
                    <tr><th className="w-20 px-3 py-3">Thứ tự</th><th className="w-48 px-3 py-3">Loại quân</th>{manualArmy.enabled ? <th className="w-36 px-3 py-3">Quân hiện có</th> : null}<th className="w-32 px-3 py-3">Số lượng thả</th><th className="w-32 px-3 py-3">Tối đa tap</th><th className="w-28 px-3 py-3">Delay</th><th className="w-36 px-3 py-3 text-right">Thao tác</th></tr>
                  </thead>
                  <tbody>
                    {sequence.map((step: any, index: number) => (
                      <tr key={`${step.slot}-${index}`} className="border-t border-white/10 bg-ink-900/60 align-top">
                        <td className="px-3 py-3 font-mono text-slate-400">{index + 1}</td>
                        <td className="px-3 py-3"><SelectInput label="" aria-label="Loại quân" value={step.slot ?? ""} options={troopOptions} onChange={(event) => updateStep(index, "slot", event.target.value)} /></td>
                        {manualArmy.enabled ? <td className="px-3 py-3"><TextInput label="" aria-label={`Số ${troopLabels[step.slot] ?? step.slot} hiện có`} type="number" min={0} max={appConfig.slot_detection?.count_max_by_kind?.[step.slot] ?? 99} value={String(manualArmy.counts?.[step.slot] ?? 0)} onChange={(event) => updatePath(["manual_army", "counts", step.slot], numberValue(event.target.value))} /></td> : null}
                        <td className="px-3 py-3"><TextInput label="" aria-label="Số lượng thả" value={String(step.count ?? "all")} onChange={(event) => updateStep(index, "count", event.target.value.trim().toLowerCase() === "all" ? "all" : numberValue(event.target.value))} /></td>
                        <td className="px-3 py-3"><TextInput label="" aria-label="Tối đa tap" type="number" min={0} value={String(step.max_taps ?? 0)} onChange={(event) => updateStep(index, "max_taps", numberValue(event.target.value))} /></td>
                        <td className="px-3 py-3"><TextInput label="" aria-label="Delay tính bằng giây" type="number" min={0} step={0.01} value={String(step.delay ?? 0)} onChange={(event) => updateStep(index, "delay", Number(event.target.value || 0))} /></td>
                        <td className="px-3 py-3"><div className="flex justify-end gap-1"><Button size="sm" variant="ghost" disabled={index === 0} aria-label="Đưa lên" onClick={() => moveStep(index, -1)}><ArrowUp className="h-4 w-4" /></Button><Button size="sm" variant="ghost" disabled={index === sequence.length - 1} aria-label="Đưa xuống" onClick={() => moveStep(index, 1)}><ArrowDown className="h-4 w-4" /></Button><Button size="sm" variant="ghost" aria-label="Xóa dòng" onClick={() => removeStep(index)}><Trash2 className="h-4 w-4 text-rose-300" /></Button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="Sequence đang trống" description="Thêm ít nhất một dòng quân trước khi chạy combo." />}
            <Button className="mt-4" variant="primary" onClick={addStep}><Plus className="h-4 w-4" />Thêm dòng quân</Button>
            {manualArmy.enabled && supplementalManualKinds.length ? (
              <div className="mt-5 border-t border-white/10 pt-5">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {supplementalManualKinds.map((kind) => (
                    <TextInput
                      key={kind}
                      type="number"
                      min={0}
                      max={appConfig.slot_detection?.count_max_by_kind?.[kind] ?? 99}
                      label={troopLabels[kind] ?? kind}
                      value={String(manualArmy.counts?.[kind] ?? 0)}
                      onChange={(event) => updatePath(["manual_army", "counts", kind], numberValue(event.target.value))}
                    />
                  ))}
                </div>
              </div>
            ) : null}
          </Card>
        </div>
      </div>

      <ConfirmModal open={Boolean(pendingDelete)} title={pendingDelete?.type === "combo" ? "Xóa combo?" : "Xóa loại lính?"} description={deleteDescription} onClose={() => setPendingDelete(null)} onConfirm={() => { if (pendingDelete?.type === "combo") deleteCombo(pendingDelete.value); else if (pendingDelete) deleteTroopKind(pendingDelete.value); setPendingDelete(null); }} />
    </div>
  );
}
