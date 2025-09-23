import pandas as pd
import time
import re
import os


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
    
    # 收集所有可能的标签匹配，按长度排序（长的优先）
    all_matches = []
    
    # 遍历所有标签分类
    for category, tags in tag_library.items():
        for tag in tags:
            # 检查基金名称中是否包含该标签
            if tag in fund_name:
                all_matches.append((tag, category, len(tag)))
    
    # 按标签长度降序排序，优先匹配更长的标签
    all_matches.sort(key=lambda x: x[2], reverse=True)
    
    # 选择不重叠的标签
    used_positions = set()
    
    for tag, category, length in all_matches:
        # 找到标签在基金名称中的位置
        start_pos = fund_name.find(tag)
        if start_pos != -1:
            # 检查是否与已选择的标签重叠
            tag_positions = set(range(start_pos, start_pos + length))
            if not tag_positions.intersection(used_positions):
                if tag not in matched_tags:  # 避免重复
                    matched_tags.append(tag)
                    matched_categories.append(category)
                    used_positions.update(tag_positions)
                    
                    # 最多匹配2个标签
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
        'QDII-股票', 'QDII-债券', '商品型-非QDII', '混合型-偏股', '股票型-标准指数', 
        '股票型-增强指数', '混合型-灵活配置', '混合型-偏债', '混合型-股债平衡', '股票型-普通'
    ]
    
    money_types = ['货币型']
    
    bond_types = [
        '债券型-中短债', '债券型-长期纯债', '债券型-短期纯债',
        '债券型-债券指数', '债券型-普通债券'
    ]
    
    # 定义基金类型到标签的映射
    fund_type_to_tag = {
        'QDII-股票': '股票',
        'QDII-债券': '债券',
        '商品型-非QDII': '商品',
        '混合型-偏股': '偏股',
        '股票型-标准指数': '指数',
        '股票型-增强指数': '指数',
        '混合型-灵活配置': '灵活',
        '混合型-偏债': '偏债',
        '混合型-股债平衡': '平衡',
        '股票型-普通': '股票'
    }
    
    print(f"   🔍 基金类型: {fund_type}")
    
    # 根据基金类型确定标签
    if fund_type in money_types:
        print(f"   💰 货币型基金，统一标签为'货币'")
        return ['货币', ''], ['货币', '']
    
    elif fund_type in bond_types:
        print(f"   📊 债券型基金，统一标签为'债券'")
        return ['债券', ''], ['债券', '']
    
    elif fund_type in stock_types:
        print(f"   📈 股票/混合型基金，先使用基金名称匹配标签")
        # 先尝试根据基金名称匹配标签
        matched_tags, matched_categories = match_tags_from_fund_name(fund_name, tag_library)
        
        # 检查是否成功匹配到标签
        if matched_tags[0] and matched_tags[0] != "":
            print(f"   ✅ 根据基金名称匹配到标签: {matched_tags[0]}, {matched_tags[1]}")
            return matched_tags, matched_categories
        else:
            # 如果根据名称找不到标签，使用基金类型映射
            type_tag = fund_type_to_tag.get(fund_type, '')
            if type_tag:
                print(f"   🏷️  根据基金类型匹配到标签: {type_tag}")
                return [type_tag, ''], [fund_type, '']
            else:
                print(f"   ❓ 未知基金类型，无法匹配标签")
                return ['', ''], ['', '']
    
    else:
        print(f"   ❓ 未知基金类型，使用基金名称匹配标签")
        return match_tags_from_fund_name(fund_name, tag_library)


def load_csv_file(file_path):
    """加载CSV文件"""
    try:
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return None
        
        # 读取CSV文件
        df = pd.read_csv(file_path)
        print(f"✅ 成功加载CSV文件: {file_path}")
        print(f"📊 共有 {len(df)} 条记录")
        print(f"📋 列名: {list(df.columns)}")
        
        return df
    except Exception as e:
        print(f"❌ 加载CSV文件失败: {str(e)}")
        return None


def save_csv_file(df, file_path):
    """保存CSV文件"""
    try:
        # 备份原文件
        backup_path = file_path.replace('.csv', '_backup.csv')
        if os.path.exists(file_path):
            import shutil
            shutil.copy2(file_path, backup_path)
            print(f"📋 已创建备份文件: {backup_path}")
        
        # 保存更新后的文件
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ 成功保存CSV文件: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 保存CSV文件失败: {str(e)}")
        return False


def update_fund_tags_in_csv(file_path):
    """主要逻辑：读取CSV文件，匹配标签并更新"""
    
    # 加载CSV文件
    df = load_csv_file(file_path)
    if df is None:
        return
    
    # 检查必要的列
    fund_name_column = None
    fund_type_column = None
    
    # 查找基金名称列
    possible_name_columns = ['基金名称', '名称', 'fund_name', 'name']
    for col in possible_name_columns:
        if col in df.columns:
            fund_name_column = col
            break
    
    # 查找基金类型列
    possible_type_columns = ['基金类型', '类型', 'fund_type', 'type']
    for col in possible_type_columns:
        if col in df.columns:
            fund_type_column = col
            break
    
    if fund_name_column is None:
        print(f"❌ 未找到基金名称列，请确保CSV文件包含以下列名之一: {possible_name_columns}")
        return
    
    print(f"📋 使用基金名称列: {fund_name_column}")
    if fund_type_column:
        print(f"📋 使用基金类型列: {fund_type_column}")
    else:
        print(f"⚠️  未找到基金类型列，将仅使用基金名称匹配标签")
    
    # 添加标签列（如果不存在）
    if '标签1' not in df.columns:
        df['标签1'] = ''
        print("✅ 已添加标签1列")
    else:
        print("✅ 标签1列已存在")
    
    if '标签2' not in df.columns:
        df['标签2'] = ''
        print("✅ 已添加标签2列")
    else:
        print("✅ 标签2列已存在")
    
    # 加载标签库
    tag_library = load_tag_library()
    if not tag_library:
        print("❌ 标签库加载失败，无法继续")
        return
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    print(f"\n🔄 开始处理 {len(df)} 条记录...")
    
    for index, row in df.iterrows():
        try:
            fund_name = str(row[fund_name_column]).strip()
            fund_type = str(row[fund_type_column]).strip() if fund_type_column else ''
            
            print(f"\n📊 处理第 {index + 1}/{len(df)} 条记录")
            print(f"   基金名称: {fund_name}")
            if fund_type:
                print(f"   基金类型: {fund_type}")
            
            # 检查基金名称是否为空
            if not fund_name or fund_name in ['nan', 'NaN', '']:
                print(f"   ⏭️  基金名称为空，跳过")
                skip_count += 1
                continue
            
            # 检查是否已有标签信息
            existing_tag1 = str(row.get('标签1', '')).strip()
            existing_tag2 = str(row.get('标签2', '')).strip()
            
            if existing_tag1 and existing_tag1 not in ['', 'nan', 'NaN'] and \
               existing_tag2 and existing_tag2 not in ['', 'nan', 'NaN']:
                print(f"   ⏭️  已有标签: {existing_tag1}, {existing_tag2}，跳过")
                skip_count += 1
                continue
            
            # 根据基金类型匹配标签
            print(f"   🔍 正在根据基金类型匹配标签...")
            matched_tags, matched_categories = match_tags_by_fund_type(fund_type, fund_name, tag_library)
            
            tag1 = matched_tags[0] if matched_tags[0] else ""
            tag2 = matched_tags[1] if matched_tags[1] else ""
            
            print(f"   📋 匹配到标签: [{tag1}], [{tag2}]")
            
            # 更新DataFrame
            df.at[index, '标签1'] = tag1
            df.at[index, '标签2'] = tag2
            
            if tag1 or tag2:
                print(f"   ✅ 成功更新标签: {tag1}, {tag2}")
                success_count += 1
            else:
                print(f"   ⚠️  未匹配到任何标签")
                error_count += 1
            
            # 添加延迟避免过快处理
            time.sleep(0.1)
                
        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断操作，已处理 {index} 条记录")
            break
        except Exception as e:
            print(f"   ❌ 处理记录时出错: {str(e)}")
            error_count += 1
            continue
    
    print(f"\n📊 处理完成！")
    print(f"✅ 成功更新: {success_count} 条记录")
    print(f"❌ 失败/无标签: {error_count} 条记录")
    print(f"⏭️  跳过: {skip_count} 条记录")
    
    # 保存更新后的文件
    if success_count > 0:
        save_success = save_csv_file(df, file_path)
        if save_success:
            print(f"✅ 文件已更新保存")
        else:
            print(f"❌ 文件保存失败")
    else:
        print(f"📋 没有记录需要更新，文件未修改")
    
    return success_count, error_count, skip_count


def main():
    """主函数"""
    print("=== 本地CSV文件基金标签更新工具 ===")
    print("💡 根据基金名称和基金类型自动匹配并更新标签信息")
    
    try:
        # 获取CSV文件路径
        default_file = "test.csv"
        file_path = input(f"请输入CSV文件路径 (回车使用默认: {default_file}): ").strip()
        
        if not file_path:
            file_path = default_file
        
        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)
        
        print(f"📁 目标文件: {file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return
        
        print(f"\n🔍 更新规则:")
        print(f"   - 读取CSV文件中所有记录的基金名称和基金类型")
        print(f"   - 使用标签库进行智能匹配")
        print(f"   - 货币型基金统一标签为'货币'")
        print(f"   - 债券型基金统一标签为'债券'")
        print(f"   - 股票/混合型基金根据名称匹配标签")
        print(f"   - 将匹配到的标签更新到CSV文件的'标签1'和'标签2'列")
        print(f"   - 如果记录已有完整标签信息，则跳过")
        print(f"   - 自动创建备份文件")
        
        # 确认更新
        confirm = input("\n确认开始更新吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 取消更新")
            return
        
        print("\n⚠️  提示: 更新过程中可以按 Ctrl+C 中断操作")
        
        # 执行更新
        update_fund_tags_in_csv(file_path)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
    except Exception as e:
        print(f"❌ 程序错误: {str(e)}")


if __name__ == "__main__":
    main()