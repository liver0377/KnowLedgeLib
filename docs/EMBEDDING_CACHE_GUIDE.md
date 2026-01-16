# HuggingFace 本地缓存配置指南

## 📋 概述

本项目已配置为强制使用 HuggingFace 本地缓存（`.hf_cache` 目录），在编码用户查询时不再需要联网下载模型。

## 🎯 主要优势

1. **离线工作**：首次下载后，所有后续操作完全离线
2. **快速启动**：无需每次启动时重新下载模型
3. **节省带宽**：避免重复下载大文件（BAAI/bge-m3 约 2GB）
4. **内存缓存**：模型加载后缓存在内存中，后续调用无需重新初始化

## 📁 目录结构

```
KnowLedgeLib/
├── .hf_cache/              # HuggingFace 模型缓存目录
│   ├── hub/               # HuggingFace Hub 缓存
│   └── transformers/       # Transformers 库模型缓存
│       └── models--BAAI--bge-m3/  # bge-m3 模型文件
└── src/
    └── core/
        └── embeddings.py    # 统一的嵌入模型管理模块
```

## ⚙️ 配置说明

### 1. 环境变量配置

在 `.env` 文件中已配置：

```bash
# HuggingFace 模型缓存目录
HF_HOME=.hf_cache
```

### 2. 代码实现

**核心模块**: `src/core/embeddings.py`

**关键功能**:

1. **强制本地缓存**
   ```python
   def _setup_huggingface_cache():
       """配置 HuggingFace 本地缓存环境变量"""
       cache_dir = os.getenv("HF_HOME", ".hf_cache")

       # 设置 HuggingFace 环境变量
       os.environ["HF_HOME"] = cache_dir
       os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(cache_dir, "hub")
       os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_dir, "transformers")
   ```

2. **内存缓存**
   ```python
   # 全局缓存变量
   _embeddings_cache: Optional[HuggingFaceEmbeddings] = None

   # 首次加载后缓存在内存中
   def get_cached_embeddings():
       # 返回缓存的实例，避免重复初始化
       return _embeddings_cache
   ```

3. **线程安全**
   ```python
   _embeddings_lock = threading.Lock()

   with _embeddings_lock:
       # 双重检查锁定模式
       if _should_reload_embeddings(...):
           _embeddings_cache = HuggingFaceEmbeddings(...)
   ```

## 🚀 使用方法

### 首次使用

1. **首次启动时**（如果本地没有缓存）:
   - 会自动从 HuggingFace Hub 下载模型
   - 模型保存到 `.hf_cache` 目录
   - 可能需要几分钟时间下载 2GB 左右的文件

2. **首次加载完成后的输出**:
   ```
   INFO: HuggingFace cache configured: D:\workspace\projects\KnowLedgeLib\.hf_cache
   INFO:   HF_HOME: D:\workspace\projects\KnowLedgeLib\.hf_cache
   INFO:   HUGGINGFACE_HUB_CACHE: D:\workspace\projects\KnowLedgeLib\.hf_cache\hub
   INFO:   TRANSFORMERS_CACHE: D:\workspace\projects\KnowLedgeLib\.hf_cache\transformers
   INFO: Loading embedding model: BAAI/bge-m3
   INFO: Model will run on device: cuda
   INFO: Embedding model loaded and cached in memory
   INFO: All HuggingFace operations will use local cache (no network access)
   ```

### 后续使用

1. **重启服务**（已有缓存）:
   - 直接从 `.hf_cache` 加载模型
   - 不需要联网
   - 启动时间显著缩短

2. **多次编码查询**:
   - 从内存缓存直接使用模型实例
   - 无需重新初始化
   - 响应速度极快

3. **日志输出**:
   ```
   INFO: Using cached embedding model from memory
   ```

## 🔍 验证本地缓存

### 方法 1: 检查缓存目录

```bash
# 查看 .hf_cache 目录内容
ls -la .hf_cache/

# 应该看到类似结构：
# .hf_cache/
# ├── hub/
# └── transformers/
#     └── models--BAAI--bge-m3/
```

### 方法 2: 运行测试脚本

```bash
# 在项目根目录运行
python test_local_cache.py
```

### 方法 3: 观察服务日志

启动服务时查看日志，确认使用本地缓存：

```bash
python -m src.run_service
```

查找这些关键日志：
- `HuggingFace cache configured: ...`
- `Using cached embedding model from memory`

## 🛠️ 常见问题

### Q1: 首次启动时是否需要联网？

**A**: 是的。如果本地没有 `.hf_cache` 或模型文件，首次启动需要从 HuggingFace Hub 下载模型（约 2GB）。

### Q2: 如何判断是否在使用本地缓存？

**A**: 查看日志输出：
- 首次加载：`Loading embedding model ...`
- 使用缓存：`Using cached embedding model from memory`

### Q3: 如何强制重新下载模型？

**A**: 删除缓存目录：
```bash
rm -rf .hf_cache
```

然后重启服务，会重新下载模型。

### Q4: 缓存文件会占用多少磁盘空间？

**A**:
- **BAAI/bge-m3 模型**: 约 2GB
- **缓存目录**: 约 2-3GB（包括元数据）

### Q5: 可以在多个项目间共享缓存吗？

**A**: 可以。只需将 `HF_HOME` 环境变量设置为同一个路径即可。

```bash
# 在多个项目的 .env 文件中设置相同的路径
HF_HOME=/path/to/shared/.hf_cache
```

### Q6: 如何完全离线使用？

**A**: 确保以下步骤完成：
1. 首次联网下载模型到 `.hf_cache`
2. 备份 `.hf_cache` 目录
3. 在离线环境恢复该目录
4. 设置 `HF_HOME` 环境变量指向该目录

### Q7: 代码修改后是否需要重新下载？

**A**: 不需要。只有当以下情况才会重新加载：
- 模型名称改变 (`EMBEDDING_MODEL_NAME`)
- 设备改变 (`EMBEDDING_DEVICE`)
- 归一化设置改变 (`NORMALIZE_EMBEDDINGS`)

## 📊 性能对比

| 操作 | 无缓存 | 本地缓存 | 内存缓存 |
|------|--------|---------|---------|
| 首次启动 | 下载 2GB + 加载 | 仅加载 | - |
| 重启服务 | 重新加载 | 仅加载 | 瞬间启动 |
| 编码查询 | 重新初始化 | 使用内存缓存 | 直接调用 |
| 网络依赖 | 每次都需要 | 仅首次 | 完全不需要 |

## 🔐 安全性

- **.gitignore**: `.hf_cache/` 已添加到 `.gitignore`，不会被提交到 Git
- **权限控制**: 确保缓存目录有适当的读写权限
- **数据隔离**: 每个环境（开发/生产）使用独立的缓存目录

## 📝 维护建议

1. **定期清理**: 如果切换了不同的模型，可以清理旧的缓存文件
2. **备份**: 对于离线部署环境，备份 `.hf_cache` 目录
3. **监控磁盘**: 注意缓存目录的磁盘空间使用情况

## 🎉 总结

通过本次优化，您的项目现在可以：

- ✅ **完全离线运行**：首次下载后不再需要联网
- ✅ **快速启动**：模型缓存在内存中，重启无需重新加载
- ✅ **节省资源**：避免重复下载和初始化
- ✅ **提高性能**：编码查询响应速度更快

享受快速、离线的嵌入服务吧！🚀
