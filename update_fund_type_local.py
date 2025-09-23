import pandas as pd
import time
import akshare as ak
import os


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


def update_fund_types_in_csv(file_path):
    """主要逻辑：读取CSV文件，获取基金代码并更新基金类型"""
    
    # 加载CSV文件
    df = load_csv_file(file_path)
    if df is None:
        return
    
    # 检查是否有基金代码列
    fund_code_column = None
    possible_columns = ['基金代码', '代码', 'fund_code', 'code']
    for col in possible_columns:
        if col in df.columns:
            fund_code_column = col
            break
    
    if fund_code_column is None:
        print(f"❌ 未找到基金代码列，请确保CSV文件包含以下列名之一: {possible_columns}")
        return
    
    print(f"📋 使用基金代码列: {fund_code_column}")
    
    # 添加基金类型列（如果不存在）
    if '基金类型' not in df.columns:
        df['基金类型'] = ''
        print("✅ 已添加基金类型列")
    else:
        print("✅ 基金类型列已存在")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    print(f"\n🔄 开始处理 {len(df)} 条记录...")
    
    for index, row in df.iterrows():
        try:
            fund_code = str(row[fund_code_column]).strip()
            
            print(f"\n📊 处理第 {index + 1}/{len(df)} 条记录")
            print(f"   基金代码: {fund_code}")
            
            # 检查基金代码是否为空
            if not fund_code or fund_code in ['nan', 'NaN', '']:
                print(f"   ⏭️  基金代码为空，跳过")
                skip_count += 1
                continue
            
            # 检查是否已有基金类型信息
            existing_fund_type = str(row.get('基金类型', '')).strip()
            if existing_fund_type and existing_fund_type not in ['', 'nan', 'NaN', '未知', '获取失败']:
                print(f"   ⏭️  已有基金类型: {existing_fund_type}，跳过")
                skip_count += 1
                continue
            
            # 获取基金类型信息
            print(f"   🔍 正在获取基金类型信息...")
            fund_type = get_fund_type_from_akshare(fund_code)
            print(f"   📋 获取到基金类型: {fund_type}")
            
            # 更新DataFrame
            df.at[index, '基金类型'] = fund_type
            
            if fund_type not in ['未知', '获取失败', '基金不存在', '代码格式错误']:
                print(f"   ✅ 成功更新基金类型: {fund_type}")
                success_count += 1
            else:
                print(f"   ⚠️  基金类型获取异常: {fund_type}")
                error_count += 1
            
            # 添加延迟避免API限制
            time.sleep(1)  # akshare API需要延迟
                
        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断操作，已处理 {index} 条记录")
            break
        except Exception as e:
            print(f"   ❌ 处理记录时出错: {str(e)}")
            error_count += 1
            continue
    
    print(f"\n📊 处理完成！")
    print(f"✅ 成功更新: {success_count} 条记录")
    print(f"❌ 失败/异常: {error_count} 条记录")
    print(f"⏭️  跳过: {skip_count} 条记录")
    
    # 保存更新后的文件
    if success_count > 0 or error_count > 0:
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
    print("=== 本地CSV文件基金类型更新工具 ===")
    print("💡 根据基金代码自动获取并更新基金类型信息")
    
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
        print(f"   - 读取CSV文件中所有记录的基金代码")
        print(f"   - 调用akshare API获取基金类型信息")
        print(f"   - 将基金类型信息更新到CSV文件的'基金类型'列")
        print(f"   - 如果记录已有基金类型信息，则跳过")
        print(f"   - 自动创建备份文件")
        
        # 确认更新
        confirm = input("\n确认开始更新吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 取消更新")
            return
        
        print("\n⚠️  提示: 更新过程中可以按 Ctrl+C 中断操作")
        print("⚠️  注意: akshare API调用较慢，请耐心等待")
        
        # 执行更新
        update_fund_types_in_csv(file_path)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
    except Exception as e:
        print(f"❌ 程序错误: {str(e)}")


if __name__ == "__main__":
    main()