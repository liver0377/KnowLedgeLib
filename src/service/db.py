"""
MySQL数据库连接和数据库访问层
用于RBAC权限管理系统
"""
import logging
from contextlib import contextmanager
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor
from core import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    上下文管理器：自动获取和释放数据库连接
    创建新的数据库连接
    """
    conn = None
    try:
        if not settings.MYSQL_HOST or not settings.MYSQL_USER or not settings.MYSQL_PASSWORD:
            raise ValueError("MySQL configuration is incomplete. Please set MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD in .env")
        
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT or 3306,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD.get_secret_value() if hasattr(settings.MYSQL_PASSWORD, 'get_secret_value') else settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DB or "knowledge_lib",
            charset=settings.MYSQL_CHARSET,
            autocommit=False,
            init_command='SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci'
        )
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


class RBACDAO:
    """RBAC权限管理数据访问对象"""
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        """根据用户名获取用户信息"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, username, password_hash, display_name, email, is_active
                    FROM users
                    WHERE username = %s AND is_active = 1
                """, (username,))
                return cursor.fetchone()
    
    @staticmethod
    def get_user_roles(user_id: int) -> list[str]:
        """获取用户的所有角色"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT r.role_key
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = %s
                """, (user_id,))
                return [row['role_key'] for row in cursor.fetchall()]
    
    @staticmethod
    def get_user_permissions(user_id: int) -> set[str]:
        """获取用户的所有权限点"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT p.perm_key
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    JOIN role_permissions rp ON r.id = rp.role_id
                    JOIN permissions p ON rp.permission_id = p.id
                    WHERE ur.user_id = %s
                """, (user_id,))
                return {row['perm_key'] for row in cursor.fetchall()}
    
    @staticmethod
    def get_user_departments(user_id: int) -> list[dict]:
        """获取用户可访问的部门及其权限"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT d.dept_key, d.name as dept_name, ud.can_read, ud.can_write
                    FROM user_departments ud
                    JOIN departments d ON ud.department_id = d.id
                    WHERE ud.user_id = %s AND d.is_active = 1
                """, (user_id,))
                return cursor.fetchall()
    
    @staticmethod
    def list_all_users() -> list[dict]:
        """列出所有用户（管理员用）"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.display_name, u.email, u.is_active
                    FROM users u
                    ORDER BY u.id
                """)
                users = cursor.fetchall()
                # 为每个用户添加角色信息
                for user in users:
                    user['roles'] = RBACDAO.get_user_roles(user['id'])
                return users
    
    @staticmethod
    def delete_user(user_id: int) -> bool:
        """删除用户（管理员用）"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 删除用户（由于外键约束，会级联删除用户角色和部门权限）
                    cursor.execute("""
                        DELETE FROM users WHERE id = %s
                    """, (user_id,))
                    
                    if cursor.rowcount == 0:
                        return False  # 用户不存在
                    
                    conn.commit()
                    return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to delete user: {e}")
                return False
    
    @staticmethod
    def update_user_roles(user_id: str, roles: list[str]) -> bool:
        """更新用户的角色"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 先删除用户的所有角色
                    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
                    
                    # 插入新角色
                    for role_key in roles:
                        cursor.execute("""
                            INSERT INTO user_roles (user_id, role_id)
                            SELECT %s, id FROM roles WHERE role_key = %s
                        """, (user_id, role_key))
                    
                    conn.commit()
                    return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to update user roles: {e}")
                return False
    
    @staticmethod
    def verify_password(hashed_password: str, plain_password: str) -> bool:
        """验证密码"""
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_all_permissions() -> list[dict]:
        """获取所有权限点"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, perm_key, name, description, resource, action, is_system
                    FROM permissions
                    ORDER BY resource, action
                """)
                return cursor.fetchall()
    
    @staticmethod
    def get_permission_by_key(perm_key: str) -> Optional[dict]:
        """根据权限标识获取权限详情"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, perm_key, name, description, resource, action, is_system
                    FROM permissions
                    WHERE perm_key = %s
                """, (perm_key,))
                return cursor.fetchone()
    
    @staticmethod
    def create_department(dept_key: str, name: str, user_id: int) -> Optional[int]:
        """创建新部门，并授予创建者完全访问权限"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 检查部门是否已存在
                    cursor.execute("""
                        SELECT id FROM departments WHERE dept_key = %s
                    """, (dept_key,))
                    if cursor.fetchone():
                        return None  # 部门已存在
                    
                    # 插入新部门
                    cursor.execute("""
                        INSERT INTO departments (dept_key, name, is_active)
                        VALUES (%s, %s, 1)
                    """, (dept_key, name))
                    dept_id = cursor.lastrowid
                    
                    # 给创建者授予完全访问权限
                    cursor.execute("""
                        INSERT INTO user_departments (user_id, department_id, can_read, can_write)
                        VALUES (%s, %s, 1, 1)
                    """, (user_id, dept_id))
                    
                    conn.commit()
                    return dept_id
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to create department: {e}")
                return None
    
    @staticmethod
    def delete_file(dept_key: str, filename: str) -> bool:
        """删除指定部门的文件（仅从文件系统删除，不涉及数据库记录）"""
        import os
        from pathlib import Path
        from core import settings
        
        # 获取知识库根目录
        kb_root = getattr(settings, "KB_FILES_ROOT", None) or os.getenv("KB_FILES_ROOT") or "./kb_files"
        root = Path(kb_root).resolve()
        
        # 构建文件路径
        file_path = root / dept_key / filename
        
        try:
            if file_path.exists() and file_path.is_file():
                os.remove(file_path)
                logger.info(f"File deleted: {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    @staticmethod
    def list_all_departments() -> list[dict]:
        """获取所有启用的部门列表"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, dept_key, name, description, parent_id, is_active
                    FROM departments
                    WHERE is_active = 1
                    ORDER BY dept_key
                """)
                return cursor.fetchall()
    
    @staticmethod
    def create_pending_user(username: str, password: str, display_name: str, email: str | None, dept_id: int | None, reason: str | None) -> Optional[int]:
        """创建待审批用户"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 检查用户名是否已存在于users或pending_users
                    cursor.execute("""
                        SELECT id FROM users WHERE username = %s
                        UNION
                        SELECT id FROM pending_users WHERE username = %s
                    """, (username, username))
                    if cursor.fetchone():
                        return None  # 用户名已存在
                    
                    # 生成密码哈希
                    from passlib.context import CryptContext
                    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                    password_hash = pwd_context.hash(password)
                    
                    # 插入待审批用户
                    cursor.execute("""
                        INSERT INTO pending_users (username, password_hash, display_name, email, requested_dept_id, reason)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (username, password_hash, display_name, email, dept_id, reason))
                    pending_id = cursor.lastrowid
                    
                    conn.commit()
                    return pending_id
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to create pending user: {e}")
                return None
    
    @staticmethod
    def list_pending_users() -> list[dict]:
        """获取所有待审批用户"""
        with get_db_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT pu.*, d.name as dept_name, d.dept_key
                    FROM pending_users pu
                    LEFT JOIN departments d ON pu.requested_dept_id = d.id
                    WHERE pu.status = 'pending'
                    ORDER BY pu.created_at ASC
                """)
                return cursor.fetchall()
    
    @staticmethod
    def approve_user(pending_id: int, dept_id: int, admin_id: int, comment: str | None) -> Optional[int]:
        """审批通过用户：将pending_users转移到users表"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 获取待审批用户信息
                    cursor.execute("""
                        SELECT * FROM pending_users WHERE id = %s AND status = 'pending'
                    """, (pending_id,))
                    pending_user = cursor.fetchone()
                    
                    if not pending_user:
                        return None  # 待审批用户不存在或已被处理
                    
                    # 创建正式用户
                    cursor.execute("""
                        INSERT INTO users (username, password_hash, display_name, email, is_active)
                        VALUES (%s, %s, %s, %s, 1)
                    """, (pending_user['username'], pending_user['password_hash'], 
                           pending_user['display_name'], pending_user['email']))
                    user_id = cursor.lastrowid
                    
                    # 分配默认角色（viewer）
                    cursor.execute("""
                        INSERT INTO user_roles (user_id, role_id)
                        SELECT %s, id FROM roles WHERE role_key = 'viewer'
                    """, (user_id,))
                    
                    # 分配部门权限
                    if dept_id:
                        cursor.execute("""
                            INSERT INTO user_departments (user_id, department_id, can_read, can_write)
                            VALUES (%s, %s, 1, 1)
                        """, (user_id, dept_id))
                    
                    # 更新待审批用户状态
                    cursor.execute("""
                        UPDATE pending_users 
                        SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(), review_comment = %s
                        WHERE id = %s
                    """, (admin_id, comment, pending_id))
                    
                    conn.commit()
                    return user_id
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to approve user: {e}")
                return None
    
    @staticmethod
    def reject_user(pending_id: int, admin_id: int, comment: str | None) -> bool:
        """驳回用户申请"""
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # 更新待审批用户状态
                    cursor.execute("""
                        UPDATE pending_users 
                        SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), review_comment = %s
                        WHERE id = %s AND status = 'pending'
                    """, (admin_id, comment, pending_id))
                    
                    if cursor.rowcount == 0:
                        return False  # 待审批用户不存在或已被处理
                    
                    conn.commit()
                    return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to reject user: {e}")
                return False
