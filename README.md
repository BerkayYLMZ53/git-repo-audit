# Git Repo Audit

Bir çalışma klasöründeki Git depolarını bulur ve hangi dallarda hazırlanan, değiştirilmiş, izlenmeyen veya çakışan dosyalar olduğunu gösterir. İzlenen dal yerelde kayıtlıysa kaç commit ileride veya geride olduğunu da yazar.

## Kullanım

Python 3.10+ ve Git 2.23+ ile depo kökünden çalıştır.

```powershell
python git_repo_audit.py ../projeler
python git_repo_audit.py ../projeler --depth 2 --json
python git_repo_audit.py . --depth 0 --check
```

Tarama varsayılan olarak üç klasör düzeyi iner. `--depth 0` yalnızca belirtilen klasörü kontrol eder. Git worktree dizinleri desteklenir. Çalışma ağacı olmayan depolar ve alt modül durumları kapsam dışındadır. Bir izlenmeyen klasör tek öğe sayılabilir.

Komut `fetch` çalıştırmadan yerel Git durumunu okur. İleri ve geri sayıları son kaydedilmiş izlenen dalı esas alır. Git'in isteğe bağlı dizin güncellemesi ve FSMonitor çağrısı kapatılır. Güvenilir yerel depolarda çalıştır.

Normal rapor için çıkış kodu `0` olur. `--check` ile dosya değişikliği veya dal farkı varsa `1`, okuma veya kullanım hatası varsa `2` döner.

## Test

```powershell
python -m unittest -v
```
