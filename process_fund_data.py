import pandas as pd
import akshare as ak
import time
from tqdm import tqdm

def get_fund_type(fund_code):
    """
    获取基金类型信息
    """
    try:
        # 确保基金代码是字符串格式
        fund_code_str = str(int(fund_code)).zfill(6)  # 转换为6位字符串格式
        
        # 调用akshare接口获取基金基本信息
        fund_info = ak.fund_individual_basic_info_xq(symbol=fund_code_str)
        
        # 检查返回数据的类型和结构
        if isinstance(fund_info, pd.DataFrame) and not fund_info.empty:
            # 查找基金类型信息
            fund_type_row = fund_info[fund_info['item'] == '基金类型']
            if not fund_type_row.empty:
                return fund_type_row['value'].iloc[0]
            else:
                # 如果没找到基金类型，显示所有可用的item
                available_items = fund_info['item'].tolist()
                print(f"基金 {fund_code_str} 可用项目: {available_items}")
                return "未找到基金类型项"
        else:
            return "数据为空或格式异常"
            
    except Exception as e:
        print(f"获取基金代码 {fund_code} 信息失败: {str(e)}")
        return "获取失败"

def process_fund_csv():
    """
    处理基金CSV文件，添加基金类型列
    """
    # 读取CSV文件
    csv_path = "/Users/daiweiwei/独立开发/makemoney/test.csv"
    df = pd.read_csv(csv_path)
    
    print(f"共找到 {len(df)} 条基金记录")
    
    # 获取唯一的基金代码，并过滤掉无效值
    unique_fund_codes = df['基金代码'].dropna().unique()
    # 过滤掉非数字的基金代码
    valid_fund_codes = []
    for code in unique_fund_codes:
        try:
            # 尝试转换为数字，如果成功则是有效的基金代码
            float(code)
            valid_fund_codes.append(code)
        except (ValueError, TypeError):
            print(f"跳过无效基金代码: {code}")
    
    print(f"共有 {len(valid_fund_codes)} 个有效的基金代码")
    
    # 创建基金代码到基金类型的映射字典
    fund_type_dict = {}
    
    # 遍历每个基金代码获取基金类型
    success_count = 0
    for i, fund_code in enumerate(tqdm(valid_fund_codes, desc="获取基金类型信息")):
        fund_type = get_fund_type(fund_code)
        fund_type_dict[fund_code] = fund_type
        
        if fund_type not in ['获取失败', '数据为空或格式异常', '未找到基金类型项']:
            success_count += 1
        
        # 每10个请求后显示一次进度和实时保存
        if (i + 1) % 10 == 0:
            print(f"\n已处理 {i+1}/{len(valid_fund_codes)}，成功获取 {success_count} 个")
            
            # 实时保存进度
            temp_df = df.copy()
            temp_df['基金类型'] = temp_df['基金代码'].map(fund_type_dict).fillna('未处理')
            temp_output_path = "/Users/daiweiwei/独立开发/makemoney/test_with_fund_type_temp.csv"
            temp_df.to_csv(temp_output_path, index=False, encoding='utf-8-sig')
            print(f"临时结果已保存到: {temp_output_path}")
        
        # 添加延时避免请求过于频繁
        time.sleep(1)  # 1秒延时
    
    # 将基金类型信息添加到DataFrame中
    df['基金类型'] = df['基金代码'].map(fund_type_dict).fillna('未处理')
    
    # 保存最终结果
    output_path = "/Users/daiweiwei/独立开发/makemoney/test_with_fund_type.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n处理完成！最终结果已保存到: {output_path}")
    
    # 显示基金类型统计
    print("\n基金类型统计:")
    type_counts = df['基金类型'].value_counts()
    for fund_type, count in type_counts.items():
        print(f"{fund_type}: {count}条")
    
    # 显示获取失败的基金代码
    failed_codes = [code for code, type_info in fund_type_dict.items() 
                   if type_info in ['获取失败', '数据为空或格式异常', '未找到基金类型项']]
    if failed_codes:
        print(f"\n获取失败的基金代码 ({len(failed_codes)}个): {failed_codes[:10]}{'...' if len(failed_codes) > 10 else ''}")
    
    # 显示成功获取的示例
    success_examples = [(code, type_info) for code, type_info in fund_type_dict.items() 
                       if type_info not in ['获取失败', '数据为空或格式异常', '未找到基金类型项', '未处理']][:5]
    if success_examples:
        print(f"\n成功获取的示例:")
        for code, fund_type in success_examples:
            print(f"  {code}: {fund_type}")
    
    return df

def resume_from_temp():
    """
    从临时文件恢复处理进度
    """
    temp_path = "/Users/daiweiwei/独立开发/makemoney/test_with_fund_type_temp.csv"
    try:
        temp_df = pd.read_csv(temp_path)
        if '基金类型' in temp_df.columns:
            print(f"发现临时文件，已处理的记录数: {len(temp_df[temp_df['基金类型'] != '未处理'])}")
            return temp_df
    except FileNotFoundError:
        print("未发现临时文件，从头开始处理")
    return None

if __name__ == "__main__":
    # 检查是否有临时文件可以恢复
    temp_df = resume_from_temp()
    if temp_df is not None:
        choice = input("发现临时文件，是否从上次进度继续？(y/n): ")
        if choice.lower() == 'y':
            print("从临时文件恢复...")
            # 这里可以添加从临时文件恢复的逻辑
    
    result_df = process_fund_csv()
    print("\n前5条记录预览:")
    print(result_df[['基金代码', '基金名称', '基金类型']].head())