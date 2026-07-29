import { useEffect, useMemo, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { SelectInput, TextInput } from "../components/FormControls";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

const troopLabels: Record<string, string> = {
  dragon: "Rồng điện",
  balloon: "Bóng",
  valkyrie: "Valkyrie",
  hero: "Tướng",
};

const spellKinds = new Set(["rage", "freeze", "poison"]);

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function cleanName(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function cleanKind(value: string): string {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return normalized.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function deployFromCombo(combo: any, fallbackDeploy: any) {
  return combo?.deploy ?? combo ?? fallbackDeploy ?? {};
}

function deployUsesKind(deploy: any, kind: string): boolean {
  const sequence = Array.isArray(deploy?.sequence) ? deploy.sequence : [];
  const spellGroups = Array.isArray(deploy?.spell_groups) ? deploy.spell_groups : [];
  return sequence.some((step: any) => step?.slot === kind) || spellGroups.some((group: any) => Array.isArray(group?.slots) && group.slots.includes(kind));
}

function remapDeployKind(deploy: any, oldKind: string, newKind: string) {
  const nextDeploy = clone(deploy ?? {});
  const sequence = Array.isArray(nextDeploy.sequence) ? nextDeploy.sequence : [];
  nextDeploy.sequence = sequence.map((step: any) => (step?.slot === oldKind ? { ...step, slot: newKind } : step));
  const spellGroups = Array.isArray(nextDeploy.spell_groups) ? nextDeploy.spell_groups : [];
  nextDeploy.spell_groups = spellGroups.map((group: any) => {
    const slots = Array.isArray(group?.slots) ? group.slots : [];
    return { ...group, slots: slots.map((slot: string) => (slot === oldKind ? newKind : slot)) };
  });
  return nextDeploy;
}

function removeDeployKind(deploy: any, kind: string) {
  const nextDeploy = clone(deploy ?? {});
  const sequence = Array.isArray(nextDeploy.sequence) ? nextDeploy.sequence : [];
  nextDeploy.sequence = sequence.filter((step: any) => step?.slot !== kind);
  const spellGroups = Array.isArray(nextDeploy.spell_groups) ? nextDeploy.spell_groups : [];
  nextDeploy.spell_groups = spellGroups.map((group: any) => {
    const slots = Array.isArray(group?.slots) ? group.slots : [];
    return { ...group, slots: slots.filter((slot: string) => slot !== kind) };
  });
  return nextDeploy;
}

function comboDeployCopy(deploy: any) {
  const nextDeploy = clone(deploy ?? {});
  delete nextDeploy.deploy_zones;
  delete nextDeploy.spell_groups;
  return nextDeploy;
}

export function ComboPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  const comboNames = useMemo(() => Object.keys(config?.combos ?? {}), [config]);
  const runningCombo = config?.farm?.combo ?? "";
  const activeCombo = "";
  const [selectedCombo, setSelectedCombo] = useState("");
  const currentCombo = selectedCombo || runningCombo || comboNames[0] || activeCombo;
  const [newComboName, setNewComboName] = useState("");
  const [comboNameDraft, setComboNameDraft] = useState("");
  const [newKindName, setNewKindName] = useState("");
  const [editingKind, setEditingKind] = useState("");
  const [kindNameDraft, setKindNameDraft] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setComboNameDraft(currentCombo);
  }, [currentCombo]);

  if (loading) {
    return <Card title="Combo">Đang tải cấu hình...</Card>;
  }
  if (!config) {
    return <Card title="Combo">{error || "Không tải được cấu hình."}</Card>;
  }

  const appConfig = config;
  const combo = appConfig.combos?.[currentCombo] ?? null;
  const deploy = deployFromCombo(combo, appConfig.deploy);
  const sequence = Array.isArray(deploy.sequence) ? deploy.sequence : [];
  const allKinds = appConfig.slot_detection?.kinds ?? ["dragon", "balloon", "valkyrie", "hero", "rage", "freeze"];
  const troopKinds = allKinds.filter((kind: string) => !spellKinds.has(kind));
  const troopOptions = troopKinds.map((kind: string) => ({ label: troopLabels[kind] ?? kind, value: kind }));
  const comboOptions = comboNames.map((name) => ({ label: name, value: name }));

  function setInfo(message: string) {
    setNotice(message);
  }

  function updateCombos(nextCombos: Record<string, any>) {
    setNotice("");
    updatePath(["combos"], nextCombos);
  }

  function updateDeploy(nextDeploy: any) {
    if (!currentCombo) return;
    const nextCombos = clone(appConfig.combos ?? {});
    nextCombos[currentCombo] = { ...(nextCombos[currentCombo] ?? {}), deploy: nextDeploy };
    updateCombos(nextCombos);
  }

  function setRunningCombo(name: string) {
    setSelectedCombo(name);
    updatePath(["farm", "combo"], name);
  }

  function createCombo() {
    const name = cleanName(newComboName);
    if (!name || appConfig.combos?.[name]) return;
    const nextCombos = clone(appConfig.combos ?? {});
    nextCombos[name] = { deploy: comboDeployCopy(appConfig.deploy ?? deploy) };
    updateCombos(nextCombos);
    setRunningCombo(name);
    setNewComboName("");
  }

  function renameCombo() {
    const name = cleanName(comboNameDraft);
    if (!currentCombo || !name || name === currentCombo) return;
    if (appConfig.combos?.[name]) {
      setInfo("Tên combo đã tồn tại.");
      return;
    }
    const nextCombos = clone(appConfig.combos ?? {});
    nextCombos[name] = nextCombos[currentCombo];
    delete nextCombos[currentCombo];
    updateCombos(nextCombos);
    if (runningCombo === currentCombo) updatePath(["farm", "combo"], name);
    setSelectedCombo(name);
  }

  function copyCombo() {
    if (!currentCombo) return;
    let copyName = `${currentCombo} Copy`;
    let index = 2;
    while (appConfig.combos?.[copyName]) {
      copyName = `${currentCombo} Copy ${index}`;
      index += 1;
    }
    const nextCombos = clone(appConfig.combos ?? {});
    nextCombos[copyName] = clone(nextCombos[currentCombo]);
    if (nextCombos[copyName]?.deploy) {
      delete nextCombos[copyName].deploy.deploy_zones;
      delete nextCombos[copyName].deploy.spell_groups;
    }
    updateCombos(nextCombos);
    setRunningCombo(copyName);
  }

  function deleteCombo() {
    if (!currentCombo || comboNames.length <= 1) return;
    const nextCombos = clone(appConfig.combos ?? {});
    delete nextCombos[currentCombo];
    const fallback = Object.keys(nextCombos)[0] ?? "";
    updateCombos(nextCombos);
    setRunningCombo(fallback);
  }

  function createTroopKind() {
    const kind = cleanKind(newKindName);
    if (!kind || allKinds.includes(kind)) return;
    updatePath(["slot_detection", "kinds"], [...allKinds, kind]);
    updatePath(["slot_detection", "count_max_by_kind", kind], 99);
    updatePath(["manual_army", "counts", kind], appConfig.manual_army?.counts?.[kind] ?? 0);
    setNewKindName("");
  }

  function renameTroopKind(oldKind: string) {
    const newKind = cleanKind(kindNameDraft);
    if (!newKind || newKind === oldKind) {
      setEditingKind("");
      return;
    }
    if (allKinds.includes(newKind)) {
      setInfo("Tên lính đã tồn tại.");
      return;
    }

    const nextKinds = allKinds.map((kind: string) => (kind === oldKind ? newKind : kind));
    const nextMaxByKind = clone(appConfig.slot_detection?.count_max_by_kind ?? {});
    nextMaxByKind[newKind] = nextMaxByKind[oldKind] ?? 99;
    delete nextMaxByKind[oldKind];

    const nextManualCounts = clone(appConfig.manual_army?.counts ?? {});
    nextManualCounts[newKind] = nextManualCounts[oldKind] ?? 0;
    delete nextManualCounts[oldKind];

    const nextCoordsSlots = clone(appConfig.coords?.slots ?? {});
    if (nextCoordsSlots[oldKind]) {
      nextCoordsSlots[newKind] = nextCoordsSlots[oldKind];
      delete nextCoordsSlots[oldKind];
    }

    const nextCombos = clone(appConfig.combos ?? {});
    for (const name of Object.keys(nextCombos)) {
      nextCombos[name] = { ...(nextCombos[name] ?? {}), deploy: remapDeployKind(deployFromCombo(nextCombos[name], appConfig.deploy), oldKind, newKind) };
    }

    updatePath(["slot_detection", "kinds"], nextKinds);
    updatePath(["slot_detection", "count_max_by_kind"], nextMaxByKind);
    updatePath(["manual_army", "counts"], nextManualCounts);
    updatePath(["coords", "slots"], nextCoordsSlots);
    updatePath(["deploy"], remapDeployKind(appConfig.deploy, oldKind, newKind));
    updateCombos(nextCombos);
    setEditingKind("");
    setKindNameDraft("");
  }

  function deleteTroopKind(kind: string) {
    const nextKinds = allKinds.filter((item: string) => item !== kind);
    const nextMaxByKind = clone(appConfig.slot_detection?.count_max_by_kind ?? {});
    const nextManualCounts = clone(appConfig.manual_army?.counts ?? {});
    const nextCoordsSlots = clone(appConfig.coords?.slots ?? {});
    const nextCombos = clone(appConfig.combos ?? {});
    delete nextMaxByKind[kind];
    delete nextManualCounts[kind];
    delete nextCoordsSlots[kind];
    for (const name of Object.keys(nextCombos)) {
      nextCombos[name] = { ...(nextCombos[name] ?? {}), deploy: removeDeployKind(deployFromCombo(nextCombos[name], appConfig.deploy), kind) };
    }

    updatePath(["slot_detection", "kinds"], nextKinds);
    updatePath(["slot_detection", "count_max_by_kind"], nextMaxByKind);
    updatePath(["manual_army", "counts"], nextManualCounts);
    updatePath(["coords", "slots"], nextCoordsSlots);
    updatePath(["deploy"], removeDeployKind(appConfig.deploy, kind));
    updateCombos(nextCombos);
    setEditingKind("");
    setInfo(`Đã xóa lính ${troopLabels[kind] ?? kind}.`);
  }

  function updateSequence(nextSequence: any[]) {
    updateDeploy({ ...deploy, sequence: nextSequence });
  }

  function updateStep(index: number, key: string, value: unknown) {
    const nextSequence = clone(sequence);
    nextSequence[index] = { ...nextSequence[index], [key]: value };
    updateSequence(nextSequence);
  }

  function addStep() {
    updateSequence([
      ...sequence,
      {
        slot: troopKinds[0] ?? "dragon",
        count: "all",
        max_taps: 10,
        delay: 0.08,
      },
    ]);
  }

  function removeStep(index: number) {
    updateSequence(sequence.filter((_: unknown, itemIndex: number) => itemIndex !== index));
  }

  return (
    <div>
      <PageHeader
        eyebrow="Combo"
        title="Thiết lập đội hình"
        subtitle="Tạo combo, thêm lính, chọn thứ tự thả quân."
        action={
          <Button variant="success" disabled={saving} onClick={save}>
            {saving ? "Đang lưu..." : "Lưu cấu hình"}
          </Button>
        }
      />

      {(error || savedMessage || notice) && (
        <div className={`mb-5 rounded-lg px-4 py-3 text-sm ${error ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
          {error || savedMessage || notice}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <div className="space-y-5">
          <Card title="1. Combo">
            <div className="space-y-4">
              <SelectInput label="Chọn combo" value={currentCombo} options={comboOptions} onChange={(event) => setSelectedCombo(event.target.value)} />
              <TextInput label="Tên combo" value={comboNameDraft} onChange={(event) => setComboNameDraft(event.target.value)} />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="primary" disabled={!currentCombo || currentCombo === runningCombo} onClick={() => setRunningCombo(currentCombo)}>
                  Dùng
                </Button>
                <Button variant="success" disabled={!currentCombo || !cleanName(comboNameDraft) || comboNameDraft === currentCombo} onClick={renameCombo}>
                  Đổi tên
                </Button>
                <Button variant="muted" disabled={!currentCombo} onClick={copyCombo}>
                  Copy
                </Button>
                <Button variant="danger" disabled={!currentCombo || comboNames.length <= 1} onClick={deleteCombo}>
                  Xóa
                </Button>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/25 p-3">
                <TextInput label="Combo mới" value={newComboName} onChange={(event) => setNewComboName(event.target.value)} />
                <Button className="mt-3 w-full" variant="success" disabled={!cleanName(newComboName) || Boolean(appConfig.combos?.[cleanName(newComboName)])} onClick={createCombo}>
                  Tạo combo
                </Button>
              </div>
            </div>
          </Card>

          <Card title="2. Lính">
            <div className="space-y-3">
              <TextInput label="Tên lính mới" value={newKindName} onChange={(event) => setNewKindName(event.target.value)} />
              <Button className="w-full" variant="success" disabled={!cleanKind(newKindName) || allKinds.includes(cleanKind(newKindName))} onClick={createTroopKind}>
                Thêm lính
              </Button>

              <div className="space-y-2">
                {troopKinds.map((kind: string) => {
                  const isEditing = editingKind === kind;
                  return (
                    <div key={kind} className="rounded-xl border border-white/10 bg-black/25 p-3">
                      {isEditing ? (
                        <div className="space-y-3">
                          <TextInput label="Tên mới" value={kindNameDraft} onChange={(event) => setKindNameDraft(event.target.value)} />
                          <div className="grid grid-cols-2 gap-2">
                            <Button variant="success" disabled={!cleanKind(kindNameDraft)} onClick={() => renameTroopKind(kind)}>
                              Lưu
                            </Button>
                            <Button variant="muted" onClick={() => setEditingKind("")}>
                              Hủy
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-white">{troopLabels[kind] ?? kind}</span>
                          <div className="flex gap-2">
                            <Button
                              className="px-3 py-1.5"
                              variant="muted"
                              onClick={() => {
                                setEditingKind(kind);
                                setKindNameDraft(kind);
                              }}
                            >
                              Sửa
                            </Button>
                            <Button className="px-3 py-1.5" variant="danger" onClick={() => deleteTroopKind(kind)}>
                              Xóa
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>

        <Card title="3. Quân trong combo">
          <div className="space-y-3">
            {sequence.length === 0 ? <p className="text-sm text-slate-500">Combo này chưa có quân.</p> : null}
            {sequence.map((step: any, index: number) => (
              <div key={`${step.slot}-${index}`} className="rounded-xl border border-white/10 bg-black/25 p-3">
                <div className="grid gap-3 md:grid-cols-[1.2fr_1fr_1fr_1fr_auto] md:items-end">
                  <SelectInput label="Loại" value={step.slot ?? ""} options={troopOptions} onChange={(event) => updateStep(index, "slot", event.target.value)} />
                  <TextInput label="Số lượng" value={String(step.count ?? "all")} onChange={(event) => updateStep(index, "count", event.target.value.trim() === "all" ? "all" : numberValue(event.target.value))} />
                  <TextInput label="Tối đa" type="number" min={0} value={String(step.max_taps ?? 0)} onChange={(event) => updateStep(index, "max_taps", numberValue(event.target.value))} />
                  <TextInput label="Delay" type="number" min={0} step={0.01} value={String(step.delay ?? 0)} onChange={(event) => updateStep(index, "delay", Number(event.target.value || 0))} />
                  <Button variant="danger" onClick={() => removeStep(index)}>
                    Xóa
                  </Button>
                </div>
              </div>
            ))}
            <Button variant="primary" onClick={addStep}>
              Thêm quân
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
