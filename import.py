import json
import csv
import os
import re
import time
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *


def get_csv_headers(csv_file_path):
    """获取CSV文件的表头"""
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        return headers


def clean_numeric_value(value):
    """清理数字值，确保可以转换为数字"""
    if not value or value == '':
        return 0
    
    # 移除所有非数字字符（除了小数点和负号）
    cleaned = re.sub(r'[^\d.-]', '', str(value))
    
    try:
        # 尝试转换为浮点数
        return float(cleaned) if cleaned else 0
    except ValueError:
        return 0


def clean_text_value(value):
    """清理文本值"""
    if value is None:
        return ""
    return str(value).strip()


def normalize_field_name(field_name):
    """标准化字段名，处理换行符等特殊字符"""
    # 移除换行符和多余空格
    normalized = re.sub(r'\s+', '', field_name.strip())
    
    # 字段名映射
    field_mapping = {
        '资产情况（结算币种）': '资产情况',
        '资产情况\n（结算币种）': '资产情况'
    }
    
    return field_mapping.get(normalized, field_name)


def get_existing_records(client, app_token, table_id, tenant_access_token):
    """获取飞书表格中的所有现有记录"""
    print("📋 正在获取飞书表格中的现有记录...")
    
    existing_records = {}
    page_token = None
    
    while True:
        try:
            # 构建查询请求
            request_builder = ListAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(500)  # 每页最多500条记录
            
            if page_token:
                request_builder.page_token(page_token)
            
            request = request_builder.build()
            option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
            response = client.bitable.v1.app_table_record.list(request, option)
            
            if not response.success():
                print(f"❌ 获取现有记录失败: {response.msg}")
                break
            
            # 处理返回的记录
            if response.data and response.data.items:
                for record in response.data.items:
                    fields = record.fields if record.fields else {}
                    fund_code = fields.get('基金代码', '')
                    trading_account = fields.get('交易账户', '')
                    
                    # 使用基金代码+交易账户作为唯一标识
                    if fund_code and trading_account:
                        key = f"{fund_code}_{trading_account}"
                        existing_records[key] = {
                            'record_id': record.record_id,
                            'fields': fields
                        }
            
            # 检查是否还有更多页
            if not response.data.has_more:
                break
            
            page_token = response.data.page_token
            time.sleep(0.1)  # 避免API限制
            
        except Exception as e:
            print(f"❌ 获取现有记录时出错: {str(e)}")
            break
    
    print(f"📋 已获取 {len(existing_records)} 条现有记录")
    return existing_records


def update_record(client, app_token, table_id, record_id, fields, tenant_access_token):
    """更新飞书表格中的记录"""
    try:
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder()
                .fields(fields)
                .build()) \
            .build()
        
        option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
        response = client.bitable.v1.app_table_record.update(request, option)
        
        return response.success(), response.msg
    except Exception as e:
        return False, str(e)


def create_record(client, app_token, table_id, fields, tenant_access_token):
    """创建新的飞书表格记录"""
    try:
        request = CreateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(AppTableRecord.builder()
                .fields(fields)
                .build()) \
            .build()
        
        option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
        response = client.bitable.v1.app_table_record.create(request, option)
        
        return response.success(), response.msg
    except Exception as e:
        return False, str(e)


def import_csv_to_feishu(app_token, table_id, csv_file_path, tenant_access_token):
    """将CSV文件导入到飞书数据表，支持条件更新"""
    # 创建client
    client = lark.Client.builder() \
        .enable_set_token(True) \
        .log_level(lark.LogLevel.INFO) \
        .build()
    
    success_count = 0
    error_count = 0
    update_count = 0
    create_count = 0
    
    print(f"开始导入CSV文件: {csv_file_path}")
    print(f"目标数据表ID: {table_id}")
    
    # 获取现有记录
    existing_records = get_existing_records(client, app_token, table_id, tenant_access_token)
    
    # 定义数字字段（根据之前的表结构）
    numeric_fields = {"序号", "持有份额", "基金净值", "资产情况"}
    
    # 读取CSV文件
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        
        for row_index, row in enumerate(csv_reader, 1):
            try:
                # 跳过空行或无效行
                if not any(row.values()) or '打印时间' in str(row):
                    print(f"跳过第{row_index}行（空行或打印时间行）")
                    continue
                
                # 清理数据，根据字段类型进行不同处理，并标准化字段名
                cleaned_row = {}
                for key, value in row.items():
                    # 标准化字段名
                    normalized_key = normalize_field_name(key)
                    
                    if normalized_key in numeric_fields:
                        # 数字字段特殊处理
                        cleaned_row[normalized_key] = clean_numeric_value(value)
                    else:
                        # 文本字段处理
                        cleaned_row[normalized_key] = clean_text_value(value)
                
                # 获取基金代码和交易账户
                fund_code = cleaned_row.get('基金代码', '')
                trading_account = cleaned_row.get('交易账户', '')
                
                if not fund_code or not trading_account:
                    print(f"⚠️  第{row_index}行缺少基金代码或交易账户，跳过")
                    continue
                
                # 构建唯一标识
                record_key = f"{fund_code}_{trading_account}"
                
                # 检查是否存在现有记录
                if record_key in existing_records:
                    # 更新现有记录
                    existing_record = existing_records[record_key]
                    record_id = existing_record['record_id']
                    
                    success, msg = update_record(client, app_token, table_id, record_id, cleaned_row, tenant_access_token)
                    
                    if success:
                        print(f"🔄 成功更新第{row_index}行数据 (基金代码: {fund_code}, 交易账户: {trading_account})")
                        update_count += 1
                        success_count += 1
                    else:
                        print(f"❌ 更新第{row_index}行失败: {msg}")
                        print(f"   数据: {cleaned_row}")
                        error_count += 1
                else:
                    # 创建新记录
                    success, msg = create_record(client, app_token, table_id, cleaned_row, tenant_access_token)
                    
                    if success:
                        print(f"➕ 成功创建第{row_index}行数据 (基金代码: {fund_code}, 交易账户: {trading_account})")
                        create_count += 1
                        success_count += 1
                    else:
                        print(f"❌ 创建第{row_index}行失败: {msg}")
                        print(f"   数据: {cleaned_row}")
                        error_count += 1
                
                # 添加延迟避免API限制
                time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print(f"\n⚠️  用户中断操作，已处理 {row_index-1} 行数据")
                break
            except Exception as e:
                print(f"❌ 处理第{row_index}行数据时出错: {str(e)}")
                error_count += 1
                continue
    
    print(f"\n📊 导入完成！")
    print(f"✅ 总成功: {success_count} 行")
    print(f"   ➕ 新创建: {create_count} 行")
    print(f"   🔄 已更新: {update_count} 行")
    print(f"❌ 失败: {error_count} 行")
    return success_count, error_count, create_count, update_count


def main():
    """主函数"""
    print("=== 飞书数据表CSV智能导入工具 ===")
    print("💡 支持基于基金代码+交易账户的条件更新")
    
    try:
        # 获取用户输入
        app_token = input("请输入App Token (回车使用默认): ").strip()
        if not app_token:
            app_token = "KizFbPWrLaS8OwsxESJc4IgxnGg"  # 默认值
            print(f"使用默认App Token: {app_token}")
        
        table_id = input("请输入Table ID: ").strip()
        if not table_id:
            print("❌ 错误: Table ID不能为空")
            return
        
        tenant_access_token = input("请输入Tenant Access Token (回车使用默认): ").strip()
        if not tenant_access_token:
            tenant_access_token = "t-g104958XY2KAUPBTACXIDYGPKS7WBOE66ZYXNBK2"  # 默认值
            print(f"使用默认Tenant Access Token")
        
        # 获取CSV文件路径
        csv_file_path = input("请输入CSV文件路径 (回车使用默认test.csv): ").strip()
        if not csv_file_path:
            csv_file_path = "/Users/daiweiwei/独立开发/makemoney/test.csv"
            print(f"使用默认CSV文件: {csv_file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(csv_file_path):
            print(f"❌ 错误: 文件不存在 - {csv_file_path}")
            return
        
        # 显示CSV文件信息
        headers = get_csv_headers(csv_file_path)
        print(f"\n📄 CSV文件信息:")
        print(f"文件路径: {csv_file_path}")
        print(f"原始表头字段: {headers}")
        print(f"标准化后字段: {[normalize_field_name(h) for h in headers]}")
        
        print(f"\n🔍 更新规则:")
        print(f"   - 如果基金代码+交易账户匹配现有记录，则更新该记录")
        print(f"   - 如果不匹配，则创建新记录")
        
        # 确认导入
        confirm = input("\n确认导入吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 取消导入")
            return
        
        print("\n⚠️  提示: 导入过程中可以按 Ctrl+C 中断操作")
        
        # 执行导入
        import_csv_to_feishu(app_token, table_id, csv_file_path, tenant_access_token)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
    except Exception as e:
        print(f"❌ 程序错误: {str(e)}")


if __name__ == "__main__":
    main()