import json
import time
import re
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from config_loader import get_feishu_config


def load_tag_library():
    """加载标签库"""
    try:
        with open('/Users/daiweiwei/独立开发/makemoney/config.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析标签库
        tag_library = {}
        lines = content.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                # 解析格式：'规模': ['中证500', '沪深300', ...]
                category = line.split(':')[0].strip().strip("'\"")
                tags_str = line.split(':', 1)[1].strip()
                
                # 提取标签列表
                tags = []
                if '[' in tags_str and ']' in tags_str:
                    tags_content = tags_str[tags_str.find('[')+1:tags_str.rfind(']')]
                    tags = [tag.strip().strip("'\"，,") for tag in tags_content.split(',') if tag.strip()]
                
                if tags:
                    tag_library[category] = tags
        
        print(f"✅ 成功加载标签库，共 {len(tag_library)} 个分类")
        for category, tags in tag_library.items():
            print(f"   {category}: {len(tags)} 个标签")
        
        return tag_library
    except Exception as e:
        print(f"❌ 加载标签库失败: {str(e)}")
        return {}


def match_tags_from_fund_name(fund_name, tag_library):
    """从基金名称中匹配标签"""
    if not fund_name or not tag_library:
        return [], []
    
    matched_tags = []
    matched_categories = []
    
    # 遍历所有标签分类
    for category, tags in tag_library.items():
        for tag in tags:
            # 检查基金名称中是否包含该标签
            if tag in fund_name:
                if tag not in matched_tags:  # 避免重复
                    matched_tags.append(tag)
                    matched_categories.append(category)
                    
                    # 最多匹配2个标签
                    if len(matched_tags) >= 2:
                        break
        
        if len(matched_tags) >= 2:
            break
    
    # 确保返回2个元素的列表
    while len(matched_tags) < 2:
        matched_tags.append("")
    
    return matched_tags[:2], matched_categories[:2]


def match_tags_by_fund_type(fund_type, fund_name, tag_library):
    """根据基金类型和基金名称匹配标签"""
    if not fund_type:
        # 如果没有基金类型，使用原有逻辑
        return match_tags_from_fund_name(fund_name, tag_library)
    
    # 定义基金类型分组
    stock_types = [
        'QDII-股票', '混合型-偏股', '股票型-标准指数', 
        '股票型-增强指数', '混合型-灵活配置', '股票型-普通'
    ]
    
    money_types = ['货币型']
    
    bond_types = [
        '债券型-中短债', '债券型-长期纯债', '债券型-短期纯债',
        '债券型-债券指数', '债券型-普通债券'
    ]
    
    print(f"   🔍 基金类型: {fund_type}")
    
    # 根据基金类型确定标签
    if fund_type in money_types:
        print(f"   💰 货币型基金，统一标签为'货币'")
        return ['货币', ''], ['货币', '']
    
    elif fund_type in bond_types:
        print(f"   📊 债券型基金，统一标签为'债券'")
        return ['债券', ''], ['债券', '']
    
    elif fund_type in stock_types:
        print(f"   📈 股票/混合型基金，使用基金名称匹配标签")
        return match_tags_from_fund_name(fund_name, tag_library)
    
    else:
        print(f"   ❓ 未知基金类型，使用基金名称匹配标签")
        return match_tags_from_fund_name(fund_name, tag_library)


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
                    fund_name = fields.get('基金名称', '')
                    fund_type = fields.get('基金类型', '')  # 新增获取基金类型
                    
                    if fund_name:  # 只处理有基金名称的记录
                        all_records.append({
                            'record_id': record.record_id,
                            'fund_name': str(fund_name),
                            'fund_type': str(fund_type),  # 新增基金类型字段
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


def update_record_with_tags(client, app_token, table_id, record_id, tag1, tag2, tenant_access_token):
    """更新记录，添加标签字段"""
    try:
        # 构建更新字段
        update_fields = {
            '标签1': tag1,
            '标签2': tag2
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


def add_tag_columns(client, app_token, table_id, tenant_access_token):
    """添加标签列到表格（如果不存在）"""
    try:
        # 首先获取表格字段信息
        request = ListAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .build()
        
        option = lark.RequestOption.builder().tenant_access_token(tenant_access_token).build()
        response = client.bitable.v1.app_table_field.list(request, option)
        
        existing_fields = []
        if response.success() and response.data and response.data.items:
            existing_fields = [field.field_name for field in response.data.items]
        
        # 检查并创建标签1列
        if '标签1' not in existing_fields:
            field_request = CreateAppTableFieldRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(AppTableField.builder()
                    .field_name("标签1")
                    .type(1)  # 1表示文本类型
                    .build()) \
                .build()
            
            field_response = client.bitable.v1.app_table_field.create(field_request, option)
            if field_response.success():
                print("✅ 成功创建标签1列")
            else:
                print(f"❌ 创建标签1列失败: {field_response.msg}")
        else:
            print("✅ 标签1列已存在")
        
        # 检查并创建标签2列
        if '标签2' not in existing_fields:
            field_request = CreateAppTableFieldRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(AppTableField.builder()
                    .field_name("标签2")
                    .type(1)  # 1表示文本类型
                    .build()) \
                .build()
            
            field_response = client.bitable.v1.app_table_field.create(field_request, option)
            if field_response.success():
                print("✅ 成功创建标签2列")
            else:
                print(f"❌ 创建标签2列失败: {field_response.msg}")
        else:
            print("✅ 标签2列已存在")
        
        return True, "标签列检查完成"
            
    except Exception as e:
        print(f"❌ 添加标签列时出错: {str(e)}")
        return False, str(e)


def update_fund_tags(app_token, table_id, tenant_access_token):
    """主要逻辑：获取基金名称并更新标签"""
    # 创建client
    client = lark.Client.builder() \
        .enable_set_token(True) \
        .log_level(lark.LogLevel.INFO) \
        .build()
    
    success_count = 0
    error_count = 0
    
    print(f"开始更新基金标签信息")
    print(f"目标数据表ID: {table_id}")
    
    # 加载标签库
    tag_library = load_tag_library()
    if not tag_library:
        print("❌ 标签库加载失败，无法继续")
        return
    
    # 添加标签列（如果不存在）
    column_success, column_msg = add_tag_columns(client, app_token, table_id, tenant_access_token)
    if not column_success:
        print(f"❌ 无法添加标签列: {column_msg}")
        return
    
    # 获取所有记录
    all_records = get_all_records(client, app_token, table_id, tenant_access_token)
    
    if not all_records:
        print("❌ 没有找到任何记录")
        return
    
    print(f"\n🔄 开始处理 {len(all_records)} 条记录...")
    
    for index, record in enumerate(all_records, 1):
        try:
            fund_name = record['fund_name']
            fund_type = record['fund_type']  # 新增获取基金类型
            record_id = record['record_id']
            
            print(f"\n📊 处理第 {index}/{len(all_records)} 条记录")
            print(f"   基金名称: {fund_name}")
            print(f"   基金类型: {fund_type}")  # 新增显示基金类型
            
            # 检查是否已有标签信息
            existing_tag1 = record['fields'].get('标签1', '')
            existing_tag2 = record['fields'].get('标签2', '')
            
            if existing_tag1 and existing_tag2:
                print(f"   ⏭️  已有标签: {existing_tag1}, {existing_tag2}，跳过")
                continue
            
            # 根据基金类型匹配标签（新逻辑）
            print(f"   🔍 正在根据基金类型匹配标签...")
            matched_tags, matched_categories = match_tags_by_fund_type(fund_type, fund_name, tag_library)
            
            tag1 = matched_tags[0] if matched_tags[0] else ""
            tag2 = matched_tags[1] if matched_tags[1] else ""
            
            print(f"   📋 匹配到标签: [{tag1}], [{tag2}]")
            
            # 删除这部分重复代码：
            # print(f"   🔍 正在匹配标签...")
            # matched_tags, matched_categories = match_tags_from_fund_name(fund_name, tag_library)
            # tag1 = matched_tags[0] if matched_tags[0] else ""
            # tag2 = matched_tags[1] if matched_tags[1] else ""
            # print(f"   📋 匹配到标签: [{tag1}], [{tag2}]")
            
            # 更新记录
            success, msg = update_record_with_tags(client, app_token, table_id, record_id, tag1, tag2, tenant_access_token)
            
            if success:
                print(f"   ✅ 成功更新标签: {tag1}, {tag2}")
                success_count += 1
            else:
                print(f"   ❌ 更新失败: {msg}")
                error_count += 1
            
            # 添加延迟避免API限制
            time.sleep(0.5)
                
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
    print("=== 飞书表格基金标签更新工具 ===")
    print("💡 根据基金名称自动匹配并更新标签信息")
    
    try:
        # 从配置文件加载默认值
        try:
            config = get_feishu_config()
            default_app_token = config['app_token']
            default_tenant_access_token = config['tenant_access_token']
            default_table_id = config['table_id']
        except Exception as e:
            print(f"⚠️  加载配置文件失败: {str(e)}")
            print("将使用手动输入模式")
            default_app_token = ""
            default_tenant_access_token = ""
            default_table_id = ""
        
        # 获取用户输入
        app_token = input(f"请输入App Token (回车使用配置文件默认值): ").strip()
        if not app_token:
            app_token = default_app_token
            if app_token:
                print(f"使用配置文件App Token: {app_token}")
            else:
                print("❌ 错误: App Token不能为空")
                return
        
        table_id = input(f"请输入Table ID (回车使用配置文件默认值): ").strip()
        if not table_id:
            table_id = default_table_id
            if table_id:
                print(f"使用配置文件Table ID: {table_id}")
            else:
                print("❌ 错误: Table ID不能为空")
                return
        
        tenant_access_token = input(f"请输入Tenant Access Token (回车使用配置文件默认值): ").strip()
        if not tenant_access_token:
            tenant_access_token = default_tenant_access_token
            if tenant_access_token:
                print(f"使用配置文件Tenant Access Token")
            else:
                print("❌ 错误: Tenant Access Token不能为空")
                return
        
        print(f"\n🔍 更新规则:")
        print(f"   - 读取表格中所有记录的基金名称")
        print(f"   - 使用标签库进行分词匹配")
        print(f"   - 将匹配到的标签更新到表格的'标签1'和'标签2'列")
        print(f"   - 如果记录已有标签信息，则跳过")
        print(f"   - 最多匹配2个标签")
        
        # 确认更新
        confirm = input("\n确认开始更新吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 取消更新")
            return
        
        print("\n⚠️  提示: 更新过程中可以按 Ctrl+C 中断操作")
        
        # 执行更新
        update_fund_tags(app_token, table_id, tenant_access_token)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
    except Exception as e:
        print(f"❌ 程序错误: {str(e)}")


if __name__ == "__main__":
    main()