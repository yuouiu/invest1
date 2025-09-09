import json
import time
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
import akshare as ak


def get_fund_type_from_akshare(fund_code):
    """通过akshare获取基金类型信息"""
    try:
        # 标准化基金代码：去除空格，补零至6位
        normalized_code = str(fund_code).strip()
        
        # 验证基金代码是否为纯数字
        if not normalized_code.isdigit():
            print(f"⚠️  基金代码格式错误: {fund_code}，应为数字")
            return "代码格式错误"
        
        # 补零至6位
        normalized_code = normalized_code.zfill(6)
        print(f"   📝 基金代码标准化: {fund_code} -> {normalized_code}")
        
        # 调用akshare API获取基金基本信息
        fund_info_df = ak.fund_individual_basic_info_xq(symbol=normalized_code)
        
        if not fund_info_df.empty:
            # 查找基金类型字段
            fund_type_row = fund_info_df[fund_info_df['item'] == '基金类型']
            
            if not fund_type_row.empty:
                fund_type = fund_type_row['value'].iloc[0]
                return str(fund_type)
            
            # 如果没有找到"基金类型"字段，尝试其他可能的字段名
            possible_type_fields = ['类型', 'fund_type', '投资类型']
            for field in possible_type_fields:
                type_row = fund_info_df[fund_info_df['item'] == field]
                if not type_row.empty:
                    fund_type = type_row['value'].iloc[0]
                    return str(fund_type)
        
        return "未知"
    except KeyError as e:
        print(f"⚠️  基金代码 {fund_code} 可能不存在或API返回格式异常: {str(e)}")
        return "基金不存在"
    except Exception as e:
        print(f"⚠️  获取基金代码 {fund_code} 的类型信息失败: {str(e)}")
        return "获取失败"


def get_all_records(client, app_token, table_id, tenant_access_token):
    """获取飞书表格中的所有记录"""
    print("📋 正在获取飞书表格中的所有记录...")
    
    all_records = []
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
                print(f"❌ 获取记录失败: {response.msg}")
                break
            
            # 处理返回的记录
            if response.data and response.data.items:
                for record in response.data.items:
                    fields = record.fields if record.fields else {}
                    fund_code = fields.get('基金代码', '')
                    
                    if fund_code:  # 只处理有基金代码的记录
                        all_records.append({
                            'record_id': record.record_id,
                            'fund_code': str(fund_code),
                            'fields': fields
                        })
            
            # 检查是否还有更多页
            if not response.data.has_more:
                break
            
            page_token = response.data.page_token
            time.sleep(0.1)  # 避免API限制
            
        except Exception as e:
            print(f"❌ 获取记录时出错: {str(e)}")
            break
    
    print(f"📋 已获取 {len(all_records)} 条有效记录")
    return all_records


def update_record_with_fund_type(client, app_token, table_id, record_id, fund_type, tenant_access_token):
    """更新记录，添加基金类型字段"""
    try:
        # 构建更新字段
        update_fields = {
            '基金类型': fund_type
        }
        
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder()
                .fields(update_fields)
                .build()) \
            .build()
        
        option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
        response = client.bitable.v1.app_table_record.update(request, option)
        
        return response.success(), response.msg
    except Exception as e:
        return False, str(e)


def add_fund_type_column(client, app_token, table_id, tenant_access_token):
    """添加基金类型列到表格（如果不存在）"""
    try:
        # 首先获取表格字段信息
        request = ListAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .build()
        
        option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
        response = client.bitable.v1.app_table_field.list(request, option)
        
        if response.success() and response.data and response.data.items:
            # 检查是否已存在基金类型字段
            existing_fields = [field.field_name for field in response.data.items]
            if '基金类型' in existing_fields:
                print("✅ 基金类型列已存在")
                return True, "字段已存在"
        
        # 创建基金类型字段
        field_request = CreateAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(AppTableField.builder()
                .field_name("基金类型")
                .type(1)  # 1表示文本类型
                .build()) \
            .build()
        
        field_response = client.bitable.v1.app_table_field.create(field_request, option)
        
        if field_response.success():
            print("✅ 成功创建基金类型列")
            return True, "字段创建成功"
        else:
            print(f"❌ 创建基金类型列失败: {field_response.msg}")
            return False, field_response.msg
            
    except Exception as e:
        print(f"❌ 添加基金类型列时出错: {str(e)}")
        return False, str(e)


def update_fund_types(app_token, table_id, tenant_access_token):
    """主要逻辑：获取基金代码并更新基金类型"""
    # 创建client
    client = lark.Client.builder() \
        .enable_set_token(True) \
        .log_level(lark.LogLevel.INFO) \
        .build()
    
    success_count = 0
    error_count = 0
    
    print(f"开始更新基金类型信息")
    print(f"目标数据表ID: {table_id}")
    
    # 添加基金类型列（如果不存在）
    column_success, column_msg = add_fund_type_column(client, app_token, table_id, tenant_access_token)
    if not column_success:
        print(f"❌ 无法添加基金类型列: {column_msg}")
        return
    
    # 获取所有记录
    all_records = get_all_records(client, app_token, table_id, tenant_access_token)
    
    if not all_records:
        print("❌ 没有找到任何记录")
        return
    
    print(f"\n🔄 开始处理 {len(all_records)} 条记录...")
    
    for index, record in enumerate(all_records, 1):
        try:
            fund_code = record['fund_code']
            record_id = record['record_id']
            
            print(f"\n📊 处理第 {index}/{len(all_records)} 条记录")
            print(f"   基金代码: {fund_code}")
            
            # 检查是否已有基金类型信息
            existing_fund_type = record['fields'].get('基金类型', '')
            if existing_fund_type and existing_fund_type not in ['', '未知', '获取失败']:
                print(f"   ⏭️  已有基金类型: {existing_fund_type}，跳过")
                continue
            
            # 获取基金类型信息
            print(f"   🔍 正在获取基金类型信息...")
            fund_type = get_fund_type_from_akshare(fund_code)
            print(f"   📋 获取到基金类型: {fund_type}")
            
            # 更新记录
            success, msg = update_record_with_fund_type(client, app_token, table_id, record_id, fund_type, tenant_access_token)
            
            if success:
                print(f"   ✅ 成功更新基金类型: {fund_type}")
                success_count += 1
            else:
                print(f"   ❌ 更新失败: {msg}")
                error_count += 1
            
            # 添加延迟避免API限制
            time.sleep(1)  # akshare API需要更长的延迟
                
        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断操作，已处理 {index-1} 条记录")
            break
        except Exception as e:
            print(f"   ❌ 处理记录时出错: {str(e)}")
            error_count += 1
            continue
    
    print(f"\n📊 更新完成！")
    print(f"✅ 成功更新: {success_count} 条记录")
    print(f"❌ 失败: {error_count} 条记录")
    return success_count, error_count


def main():
    """主函数"""
    print("=== 飞书表格基金类型更新工具 ===")
    print("💡 根据基金代码自动获取并更新基金类型信息")
    
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
            tenant_access_token = "t-g104999iBA7ONLQ3GUJHVVL27AEUMGRM2CTGW7J2"  # 默认值
            print(f"使用默认Tenant Access Token")
        
        print(f"\n🔍 更新规则:")
        print(f"   - 读取表格中所有记录的基金代码")
        print(f"   - 调用akshare API获取基金类型信息")
        print(f"   - 将基金类型信息更新到表格的'基金类型'列")
        print(f"   - 如果记录已有基金类型信息，则跳过")
        
        # 确认更新
        confirm = input("\n确认开始更新吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 取消更新")
            return
        
        print("\n⚠️  提示: 更新过程中可以按 Ctrl+C 中断操作")
        print("⚠️  注意: akshare API调用较慢，请耐心等待")
        
        # 执行更新
        update_fund_types(app_token, table_id, tenant_access_token)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
    except Exception as e:
        print(f"❌ 程序错误: {str(e)}")


if __name__ == "__main__":
    main()