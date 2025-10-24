class Config:
    # 基础配置
    DEBUG = False
    SECRET_KEY = 'your_secret_key' #可不配置
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tickethunter.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 大模型API配置-智谱
    ZHIPU_API_KEY = 'be4d3127355e4363a4fc8fdab68e1b87.IXrJwhSFGyj47Bhu' #需要填写你的智谱api
    
    # 小红书 MCP 服务配置
    MCP_XIAOHONGSHU_URL = 'http://localhost:18060/mcp'  # 本地 xiaohongshu-mcp 服务地址
    
    # 监控配置
    MONITOR_INTERVAL = 300  # 5分钟
    
    # 缓存配置
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # 限流配置
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'log/tickethunter.log'
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    LOG_MAX_BYTES = 1024 * 1024  # 1MB
    LOG_BACKUP_COUNT = 5

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tickethunter_dev.db'

class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'WARNING'
    MONITOR_INTERVAL = 600  # 10分钟 