import math

import numpy as np
import pandas as pd
from pandas_ta import ema

default_ohlcv_col = {'close': 'close', 'open': 'open', 'high': 'high', 'low': 'low', 'volume': 'volume'}


def add_tm_ema_features(input_df, fn=26, sn=9, ohlcv_col=default_ohlcv_col, fillna=False, adx_threshold=25):
    # copy dataframe
    input_df = input_df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    # close = ohlcv_col['close']
    # volume = ohlcv_col['volume']
    def tm_lambda(df, fn, sn):
        ema1 = em(series=df['H_Close'], periods=fn, fillna=fillna).mean()
        ema2 = em(series=df['H_High'], periods=sn, fillna=fillna).mean().shift(3)
        ema3 = em(series=df['H_Low'], periods=sn, fillna=fillna).mean().shift(3)
        input_df.loc[df.index, 'ema_fast_close'] = ema1
        input_df.loc[df.index, 'ema_slow_high'] = ema2
        input_df.loc[df.index, 'ema_slow_low'] = ema3
        signal_df = cal_crossover_and_boundry_signal(df=input_df.loc[df.index], fast_line='H_Close',
                                                     result_col='tm_signal',
                                                     base_line='ema_fast_close',
                                                     top_line='ema_slow_high',
                                                     bottom_line='ema_slow_low')
        input_df.loc[df.index, 'tm_signal'] = signal_df['tm_signal']

    input_df.groupby(level=0).apply(
        lambda x: tm_lambda(x, fn, sn)
    )
    return input_df


# True strength index (TSI)
#  """
#     Formula
#     -
#     TSI = (Double Smoothed PC / Double Smoothed Absolute PC) x 100
#     Double Smoothed PC
#     ------------------
#     PC = Current Price minus Prior Price
#     First Smoothing = 25-period EMA of PC
#     Second Smoothing = 13-period EMA of 25-period EMA of PC
#     Double Smoothed Absolute PC
#     ---------------------------
#     Absolute Price Change |PC| = Absolute Value of Current Price minus Prior Price
#     First Smoothing = 25-period EMA of |PC|
#     Second Smoothing = 13-period EMA of 25-period EMA of |PC|
#     """
def add_tm_tsi_features(df, r=25, s=13, ema_period=13, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate True strength index

    :param df: original OHLCV dataframe
    :param r: ma window size for high
    :param s: ma window size for low
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # Calculate Result
    diff = df[close].diff(1)
    smoothed_pc = ema(close=diff, length=r)
    double_smoothed_pc = ema(close=smoothed_pc, length=s)

    abs_diff = diff.abs()
    smoothed_abs_pc = ema(close=abs_diff, length=r)
    double_smoothed_abs_pc = ema(close=smoothed_abs_pc, length=s)

    tsi = 100 * double_smoothed_pc / double_smoothed_abs_pc
    tsi_sig = em(series=tsi, periods=ema_period).mean()

    # fill na values
    if fillna:
        tsi = tsi.replace([np.inf, -np.inf], np.nan).fillna(0)
        tsi_sig = tsi_sig.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign tsi to df
    df['tsi'] = tsi
    df['tsi_sig'] = tsi_sig

    df['tsi_log'] = df['tsi'].apply(
        lambda x: symmetric_logarithm(x)
    )
    df['tis_sig_log'] = df['tsi_sig'].apply(
        lambda x: symmetric_logarithm(x)
    )
    # calculate signal
    if cal_signal:
        df['top_border'] = 0.1
        df['bot_border'] = -0.1
        df['tm_tsi_signal'] = cal_uturn_signal(df=df, fast_line='tsi_log', spread_line='tis_sig_log',
                                               top_line='top_border', bottom_line='bot_border',
                                               result_col='log_tsi_signal', pos_signal='b', neg_signal='s',
                                               none_signal='n')

    return df

def symmetric_logarithm(arg,base=10,shift=1):
    if arg >= 0:
        return math.log(arg + shift, base) - math.log(shift, base)
    else:
        return -math.log(-arg+shift,base)+math.log(shift,base)

# add heikin-ashi candlestick features
def add_tm_heikin_ashi_features(input_df, ohlcv_col=default_ohlcv_col, replace_ohlc=False, dropna=False):
    """
    Add heikin-ashi candlestick dimentions for dataframe
    :param input_df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :returns: dataframe with candlestick columns
    :raises: none
    """
    # copy dataframe
    input_df = input_df.copy()

    # set column names
    open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']
    for entity_id, df in input_df.groupby(level=0):
        # for col in [open, high, low, close]:
        #     input_df.loc[entity_id].head(1)[f'prev_{col}'] = input_df.loc[entity_id].head(1)[col]
        pre_index = None
        pre_item = None
        # calculate heikin-ashi ohlc
        for index, item in df.iterrows():
            if pre_index is None:
                input_df.loc[index, 'H_Open'] = (input_df.loc[index, open] + input_df.loc[index, close]) / 2
            else:
                input_df.loc[index, 'H_Open'] = (input_df.loc[pre_index, 'H_Open'] + input_df.loc[
                    pre_index, 'H_Close']) / 2
            input_df.loc[index, 'H_Close'] = (input_df.loc[index, open] + input_df.loc[index, high] + input_df.loc[
                index, low] + input_df.loc[index, close]) / 4
            pre_index = index
            pre_item = item
    input_df['H_High'] = input_df[[high, 'H_Open', 'H_Close']].max(axis=1)
    input_df['H_Low'] = input_df[[low, 'H_Open', 'H_Close']].min(axis=1)

    # replace original ohlc with heikin-ashi ohlc
    if replace_ohlc:
        for col in [open, high, low, close]:
            input_df.drop(f'{col}', axis=1, inplace=True)
        input_df.rename(columns={'H_Close': close, 'H_Open': open, 'H_High': high, 'H_Low': low}, inplace=True)

    # dropna values
    if dropna:
        input_df.dropna(inplace=True)

    return input_df


# https://github.com/northcheng/quant/blob/0846c99590b6e076ba955140d029fa3ef2fd1acd/bc_technical_analysis.py

# ================================================ Basic calculation ================================================ #
# drop na values for dataframe
def dropna(df):
    """
    Drop rows with "Nans" values

    :param df: original dfframe
    :returns: dfframe with Nans dropped
    :raises: none
    """
    df = df[df < math.exp(709)]  # big number
    df = df[df != 0.0]
    df = df.dropna()
    return df


# fill na values for dataframe
def fillna(series, fill_value=0):
    """
    Fill na value for a series with specific value

    :param series: series to fillna
    :param fill_value: the value to replace na values
    :returns: series with na values filled
    :raises: none
    """
    series.replace([np.inf, -np.inf], np.nan).fillna(fill_value)
    return series


# get max/min in 2 values
def get_min_max(x1, x2, f='min'):
    """
    Get Max or Min value from 2 values

    :param x1: value 1
    :param x2: value 2
    :param f: which one do you want: max/min
    :returns: max or min value
    :raises:
    """
    if not np.isnan(x1) and not np.isnan(x2):
        if f == 'max':
            return max(x1, x2)
        elif f == 'min':
            return min(x1, x2)
        else:
            raise ValueError('"f" variable value should be "min" or "max"')
    else:
        return np.nan

    # filter index that meet conditions


def filter_idx(df, condition_dict):
    """
    # Filter index that meet conditions

    :param df: dataframe to search
    :param condition_dict: dictionary of conditions
    :returns: dictionary of index that meet corresponding conditions
    :raises: None
    """
    # target index
    result = {}
    for condition in condition_dict.keys():
        result[condition] = df.query(condition_dict[condition]).index

    # other index
    other_idx = df.index
    for i in result.keys():
        other_idx = [x for x in other_idx if x not in result[i]]
    result['other'] = other_idx

    return result


# set index-column with specific value
def set_idx_col_value(df, idx, col, values, set_on_copy=True):
    """
    Set specific index-column with specific values

    :param df: dataframe to search
    :param idx: dictionary of index
    :param col: target column
    :param values: dictionary of values, with same keys as idx
    :param set_on_copy: whether to set values on a copy of df
    :returns: dataframe with value set
    :raises: None
    """

    # copy dataframe
    if set_on_copy:
        df = df.copy()

    # set values to specific index, column
    for i in idx.keys():
        df.loc[idx[i], col] = values[i]

    return df


# ================================================ Rolling windows ================================================== #
# simple moving window
def sm(series, periods, fillna=False):
    """
    Simple Moving Window

    :param series: series to roll
    :param periods: size of the moving window
    :param fillna: make the min_periods = 0
    :returns: a rolling window with window size 'periods'
    :raises: none
    """
    if fillna:
        return series.rolling(window=periods, min_periods=0)
    return series.rolling(window=periods, min_periods=periods)


# exponential moving window
def em(series, periods, fillna=False):
    """
    Exponential Moving Window

    :param series: series to roll
    :param periods: size of the moving window
    :param fillna: make the min_periods = 0
    :returns: an exponential weighted rolling window with window size 'periods'
    :raises: none
    """
    if fillna:
        return series.ewm(span=periods, min_periods=0)
    return series.ewm(span=periods, min_periods=periods)


# same direction accumulation
def sda(series, zero_as=None):
    """
    Accumulate value with same symbol (+/-), once the symbol changed, start over again

    :param series: series to calculate
    :param accumulate_by: if None, accumulate by its own value, other wise, add by specified value
    :param zero_val: action when encounter 0: if None pass, else add(minus) spedicied value according to previous symbol
    :returns: series with same direction accumulation
    :raises: None
    """
    # copy series
    target_col = series.name
    index_col = series.index.name
    new_series = series.reset_index()

    previous_idx = None
    current_idx = None
    for index, row in new_series.iterrows():

        # record current index
        current_idx = index

        # for the first loop
        if previous_idx is None:
            pass

        # for the rest of loops
        else:
            current_val = new_series.loc[current_idx, target_col]
            previous_val = new_series.loc[previous_idx, target_col]

            # with same direction
            if current_val * previous_val > 0:
                new_series.loc[current_idx, target_col] = current_val + previous_val

            # current value is 0 and previous value is not 0
            elif current_val == 0 and previous_val != 0:
                if zero_as is not None:
                    if previous_val > 0:
                        new_series.loc[current_idx, target_col] = previous_val + zero_as
                    else:
                        new_series.loc[current_idx, target_col] = previous_val - zero_as

            # otherwise(different direction, previous(and current) value is 0)
            else:
                pass

        # record previous index
        previous_idx = index

    # reset index back
    new_series = new_series.set_index(index_col)[target_col].copy()

    return new_series


# ================================================ Change calculation =============================================== #
# calculate change of a column in certain period
def cal_change(df, target_col, periods=1, add_accumulation=True, add_prefix=False, drop_na=False):
    """
    Calculate change of a column with a sliding window

    :param df: original dfframe
    :param target_col: change of which column to calculate
    :param periods: calculate the change within the period
    :param add_accumulation: wether to add accumulative change in a same direction
    :param add_prefix: whether to add prefix for the result columns (when there are multiple target columns to calculate)
    :param drop_na: whether to drop na values from dataframe:
    :returns: dataframe with change rate columns
    :raises: none
    """
    # copy dateframe
    df = df.copy()

    # set prefix for result columns
    prefix = ''
    if add_prefix:
        prefix = f'{target_col}_'

    # set result column names
    change_col = f'{prefix}change'
    acc_change_col = f'{prefix}acc_change'
    acc_change_count_col = f'{prefix}acc_change_count'

    # calculate change within the period
    df[change_col] = df[target_col].diff(periods=periods)

    # calculate accumulative change in a same direction
    if add_accumulation:
        df[acc_change_col] = sda(series=df[change_col], zero_as=0)

        df[acc_change_count_col] = 0
        df.loc[df[change_col] > 0, acc_change_count_col] = 1
        df.loc[df[change_col] < 0, acc_change_count_col] = -1
        df[acc_change_count_col] = sda(series=df[acc_change_count_col], zero_as=1)

    # drop NA values
    if drop_na:
        df.dropna(inplace=True)

    return df


# calculate change rate of a column in certain period
def cal_change_rate(df, target_col, periods=1, add_accumulation=True, add_prefix=False, drop_na=False):
    """
    Calculate change rate of a column with a sliding window

    :param df: original dfframe
    :param target_col: change rate of which column to calculate
    :param periods: calculate the change rate within the period
    :param add_accumulation: wether to add accumulative change rate in a same direction
    :param add_prefix: whether to add prefix for the result columns (when there are multiple target columns to calculate)
    :param drop_na: whether to drop na values from dataframe:
    :returns: dataframe with change rate columns
    :raises: none
    """
    # copy dfframe
    df = df.copy()

    # set prefix for result columns
    prefix = ''
    if add_prefix:
        prefix = f'{target_col}_'

    # set result column names
    rate_col = f'{prefix}rate'
    acc_rate_col = f'{prefix}acc_rate'
    acc_day_col = f'{prefix}acc_day'

    # calculate change rate within the period
    df[rate_col] = df[target_col].pct_change(periods=periods)

    # calculate accumulative change rate in a same direction
    if add_accumulation:
        df[acc_rate_col] = 0
        df.loc[df[rate_col] >= 0, acc_day_col] = 1
        df.loc[df[rate_col] < 0, acc_day_col] = -1

        # go through each row, add values with same symbols (+/-)
        idx = df.index.tolist()
        for i in range(1, len(df)):
            current_idx = idx[i]
            previous_idx = idx[i - 1]
            current_rate = df.loc[current_idx, rate_col]
            previous_acc_rate = df.loc[previous_idx, acc_rate_col]
            previous_acc_days = df.loc[previous_idx, acc_day_col]

            if previous_acc_rate * current_rate > 0:
                df.loc[current_idx, acc_rate_col] = current_rate + previous_acc_rate
                df.loc[current_idx, acc_day_col] += previous_acc_days
            else:
                df.loc[current_idx, acc_rate_col] = current_rate

    if drop_na:
        df.dropna(inplace=True)

    return df


# ================================================ Signal processing ================================================ #
# calculate signal that generated from 2 lines crossover
def cal_crossover_signal(df, fast_line, slow_line, result_col='signal', pos_signal='b', neg_signal='s',
                         none_signal='n'):
    """
    Calculate signal generated from the crossover of 2 lines
    When fast line breakthrough slow line from the bottom, positive signal will be generated
    When fast line breakthrough slow line from the top, negative signal will be generated

    :param df: original dffame which contains a fast line and a slow line
    :param fast_line: columnname of the fast line
    :param slow_line: columnname of the slow line
    :param result_col: columnname of the result
    :param pos_signal: the value of positive signal
    :param neg_signal: the value of negative signal
    :param none_signal: the value of none signal
    :returns: series of the result column
    :raises: none
    """
    df = df.copy()

    # calculate the distance between fast and slow line
    df['diff'] = df[fast_line] - df[slow_line]
    df['diff_prev'] = df['diff'].shift(1)

    # get signals from fast/slow lines cross over
    df[result_col] = none_signal
    pos_idx = df.query('(diff >= 0 and diff_prev < 0) or (diff > 0 and diff_prev <= 0)').index
    neg_idx = df.query('(diff <= 0 and diff_prev > 0) or (diff < 0 and diff_prev >= 0)').index

    # assign signal values
    df[result_col] = none_signal
    df.loc[pos_idx, result_col] = pos_signal
    df.loc[neg_idx, result_col] = neg_signal

    return df[[result_col]]

def cal_uturn_signal(df, fast_line, spread_line, top_line, bottom_line, result_col='signal', pos_signal='b', neg_signal='s',
                     none_signal='n'):
    """
    Calculate signal generated from the crossover of 2 lines
    When fast line breakthrough top_line from the bottom and spread_line still under bottom line, positive signal will be generated
    When fast line breakthrough bottom_line from the top, and spread_line still above top line,negative signal will be generated

    :param df: original dffame which contains a fast line and a slow line
    :param fast_line: columnname of the fast line
    :param spread_line: columnname of the spread_line line
    :param top_line: columnname of the spread_line line
    :param bottom_line: columnname of the spread_line line
    :param result_col: columnname of the result
    :param pos_signal: the value of positive signal
    :param neg_signal: the value of negative signal
    :param none_signal: the value of none signal
    :returns: series of the result column
    :raises: none
    """
    df = df.copy()

    # calculate the distance between fast and slow line
    df['diff_fast_top'] = df[fast_line] - df[top_line]
    df['diff_diff_fast_top_prev'] = df['diff_fast_top'].shift(1)
    df['diff_spread_bot'] = df[spread_line] - df[bottom_line]

    df['diff_fast_bot'] = df[fast_line] - df[bottom_line]
    df['diff_fast_bot_prev'] = df['diff_fast_bot'].shift(1)
    df['diff_spread_top'] = df[spread_line] - df[top_line]

    # get signals from fast/slow lines cross over
    df[result_col] = none_signal
    # 上升信号
    pos_idx = df.query('(diff_fast_bot >= 0 and diff_fast_bot_prev < 0 and diff_spread_top >= 0) or (diff_fast_bot > 0 and diff_fast_bot_prev <= 0 and diff_spread_top >= 0)').index
    # 下降信号
    neg_idx = df.query('(diff_fast_top <= 0 and diff_diff_fast_top_prev > 0 and diff_spread_bot <= 0) or (diff_fast_top < 0 and diff_diff_fast_top_prev >= 0 and diff_spread_bot <= 0)').index

    # assign signal values
    df[result_col] = none_signal
    df.loc[pos_idx, result_col] = pos_signal
    df.loc[neg_idx, result_col] = neg_signal

    return df[[result_col]]

def cal_crossover_and_boundry_signal(df, fast_line, base_line, top_line, bottom_line, result_col='signal', pos_signal='b', neg_signal='s',
                         none_signal='n'):
    """
    Calculate signal generated from the crossover of 4 lines
    When fast line breakthrough base line and top line from the bottom, positive signal will be generated
    When fast line breakthrough base line and bottom line from the top, negative signal will be generated

    :param df: original dffame which contains a fast line and a slow line
    :param fast_line: columnname of the fast line
    :param base_line: columnname of the fast line
    :param top_line: columnname of the top line
    :param bottom_line: columnname of the bottom line
    :param result_col: columnname of the result
    :param pos_signal: the value of positive signal
    :param neg_signal: the value of negative signal
    :param none_signal: the value of none signal
    :returns: series of the result column
    :raises: none
    """
    df = df.copy()

    # calculate the distance between fast and slow line
    df['diff1'] = df[fast_line] - df[base_line]
    df['diff_prev1'] = df['diff1'].shift(1)

    df['diff2'] = df[fast_line] - df[top_line]
    df['diff_prev2'] = df['diff2'].shift(1)

    df['diff3'] = df[fast_line] - df[bottom_line]
    df['diff_prev3'] = df['diff3'].shift(1)

    # get signals from fast/slow lines cross over
    df[result_col] = none_signal
    pos_idx = df.query('(diff1 >= 0 and diff2 >= 0) and (diff_prev1 <= 0 or diff_prev2 <= 0)').index
    neg_idx = df.query('(diff1 <= 0 and diff3 <= 0) and (diff_prev1 >= 0 or diff_prev2 >= 0)').index

    # assign signal values
    df[result_col] = none_signal
    df.loc[pos_idx, result_col] = pos_signal
    df.loc[neg_idx, result_col] = neg_signal

    return df[[result_col]]

# calculate signal that generated from trigering boundaries
def cal_boundary_signal(df, upper_col, lower_col, upper_boundary, lower_boundary, result_col='signal', pos_signal='b',
                        neg_signal='s', none_signal='n'):
    """
    Calculate signal generated from triger of boundaries
    When upper_col breakthrough upper_boundary, positive signal will be generated
    When lower_col breakthrough lower_boundary, negative signal will be generated

    :param df: original dffame which contains a fast line and a slow line
    :param upper_col: columnname of the positive column
    :param lower_col: columnname of the negative column
    :param upper_boundary: upper boundary
    :param lower_boundary: lower boundary
    :param result_col: columnname of the result
    :param pos_signal: the value of positive signal
    :param neg_siganl: the value of negative signal
    :param none_signal: the value of none signal
    :returns: series of the result column
    :raises: none
    """
    # copy dataframe
    df = df.copy()

    # calculate signals
    pos_idx = df.query(f'{upper_col} > {upper_boundary}').index
    neg_idx = df.query(f'{lower_col} < {lower_boundary}').index

    # assign signal values
    df[result_col] = none_signal
    df.loc[pos_idx, result_col] = pos_signal
    df.loc[neg_idx, result_col] = neg_signal

    return df[[result_col]]


# replace signal values
def replace_signal(df, signal_col='signal', replacement={'b': 1, 's': -1, 'n': 0}):
    """
    Replace signals with different values
    :param df: df that contains signal column
    :param signal_col: column name of the signal
    :param replacement: replacement, key is original value, value is the new value
    :returns: df with signal values replaced
    :raises: none
    """
    # copy dataframe
    new_df = df.copy()

    # find and replace
    for i in replacement.keys():
        new_df[signal_col].replace(to_replace=i, value=replacement[i], inplace=True)

    return new_df


# remove duplicated signals
def remove_redundant_signal(df, signal_col='signal', pos_signal='b', neg_signal='s', none_signal='n', keep='first'):
    """
    Remove redundant (duplicated continuous) signals, keep only the first or the last one

    :param df: signal dataframe
    :param signal_col: columnname of the signal value
    :param keep: which one to keep: first/last
    :param pos_signal: the value of positive signal
    :param neg_siganl: the value of negative signal
    :param none_signal: the value of none signal
    :returns: signal dataframe with redundant signal removed
    :raises: none
    """
    # copy dataframe
    df = df.copy()

    # initialize
    signals = df.query(f'{signal_col} != "{none_signal}"').copy()
    movement = {'first': 1, 'last': -1}.get(keep)

    # find duplicated signals and set to none_signal
    if len(signals) > 0 and movement is not None:
        signals['is_dup'] = signals[signal_col] + signals[signal_col].shift(movement)
        dup_idx = signals.query(f'is_dup == "{pos_signal}{pos_signal}" or is_dup == "{neg_signal}{neg_signal}"').index

        if len(dup_idx) > 0:
            df.loc[dup_idx, signal_col] = none_signal

    return df


# ================================================ Self-defined TA ================================================== #
# linear regression
# def linear_fit(df, target_col, periods):
#     """
#     Calculate slope for selected piece of data
#
#     :param df: dataframe
#     :param target_col: target column name
#     :param periods: input data length
#     :returns: slope of selected data from linear regression
#     :raises: none
#     """
#
#     if len(df) <= periods:
#         return {'slope': 0, 'intecept': 0}
#
#     else:
#         x = range(1, periods + 1)
#         y = df[target_col].fillna(0).tail(periods).values.tolist()
#         lr = linregress(x, y)
#
#         return {'slope': lr[0], 'intecept': lr[1]}


# calculate peak / trough in price
# def cal_peak_trough(df, target_col, height=None, threshold=None, distance=None, width=None):
#     """
#     Calculate the position (signal) of the peak/trough of the target column
#
#     :param df: original dataframe which contains target column
#     :param result_col: columnname of the result
#     :param peak_signal: the value of the peak signal
#     :param trough_signal: the value of the trough signal
#     :param none_signal: the value of the none signal
#     :further_filter: if the peak/trough value is higher/lower than the average of its former and later peak/trough values, this peak/trough is valid
#     :returns: series of peak/trough signal column
#     :raises: none
#     """
#     # copy dataframe
#     df = df.copy()
#
#     # set result values
#     result_col = 'signal'
#     peak_signal = 'p'
#     trough_signal = 't'
#     none_signal = 'n'
#
#     try:
#         # find peaks
#         peaks, _ = find_peaks(df[target_col], height=height, threshold=threshold, distance=distance, width=width)
#         peaks = df.iloc[peaks,].index
#
#         # find troughs
#         troughs, _ = find_peaks(-df[target_col], height=height, threshold=threshold, distance=distance, width=width)
#         troughs = df.iloc[troughs,].index
#
#         # set signal values
#         df[result_col] = none_signal
#         df.loc[peaks, result_col] = peak_signal
#         df.loc[troughs, result_col] = trough_signal
#
#     except Exception as e:
#         print(e, 'using self-defined method')
#
#         further_filter = True
#
#         # previous value of the target column
#         previous_target_col = 'previous_' + target_col
#         df[previous_target_col] = df[target_col].shift(1)
#
#         # when value goes down, it means it is currently at peak
#         peaks = df.query(f'{target_col} < {previous_target_col}').index
#         # when value goes up, it means it is currently at trough
#         troughs = df.query(f'{target_col} > {previous_target_col}').index
#
#         # set signal values
#         df[result_col] = none_signal
#         df.loc[peaks, result_col] = peak_signal
#         df.loc[troughs, result_col] = trough_signal
#
#         # shift the signal back by 1 unit
#         df[result_col] = df[result_col].shift(-1)
#
#         # remove redundant signals
#         df = remove_redundant_signal(df=df, signal_col=result_col, keep='first', pos_signal=peak_signal,
#                                      neg_signal=trough_signal, none_signal=none_signal)
#
#         # further filter the signals
#         if further_filter:
#
#             # get all peak/trough signals
#             peak = df.query(f'{result_col}=="{peak_signal}"').index.tolist()
#             trough = df.query(f'{result_col}=="{trough_signal}"').index.tolist()
#
#             # peak/trough that not qualified
#             false_peak = []
#             false_trough = []
#
#             # filter peak signals
#             for i in range(len(peak)):
#                 current_idx = peak[i]
#                 benchmark = 0
#
#                 # the peak is not qualified if it is lower that the average of previous 2 troughs
#                 previous_troughs = df[:current_idx].query(f'{result_col}=="{trough_signal}"').tail(2)
#                 if len(previous_troughs) > 0:
#                     benchmark = previous_troughs[target_col].mean()
#
#                 if df.loc[current_idx, target_col] < benchmark:
#                     false_peak.append(current_idx)
#
#             # filter trough signals
#             for i in range(len(trough)):
#                 current_idx = trough[i]
#                 benchmark = 0
#
#                 # the trough is not qualified if it is lower that the average of previous 2 peaks
#                 previous_peaks = df[:current_idx].query(f'{result_col}=="{peak_signal}"').tail(2)
#                 if len(previous_peaks) > 0:
#                     benchmark = previous_peaks[target_col].mean()
#
#                 if df.loc[current_idx, target_col] > benchmark:
#                     false_trough.append(current_idx)
#
#             df.loc[false_peak, result_col] = none_signal
#             df.loc[false_trough, result_col] = none_signal
#             df.fillna('n')
#
#     return df[[result_col]]


# calculate moving average
def cal_moving_average(df, target_col, ma_windows=[50, 105], start=None, end=None, window_type='em'):
    """
    Calculate moving average of the tarhet column with specific window size

    :param df: original dataframe which contains target column
    :param ma_windows: a list of moving average window size to be calculated
    :param start: start date of the data
    :param end: end date of the data
    :param window_type: which moving window to be used: sm/em
    :returns: dataframe with moving averages
    :raises: none
    """
    # copy dataframe
    df = df[start:end].copy()

    # select moving window type
    if window_type == 'em':
        mw_func = em
    elif window_type == 'sm':
        mw_func = sm
    else:
        print('Unknown moving window type')
        return df

    # calculate moving averages
    for mw in ma_windows:
        ma_col = f'{target_col}_ma_{mw}'
        df[ma_col] = mw_func(series=df[target_col], periods=mw).mean()

    return df


# add candle stick features
def add_candlestick_features(df, ohlcv_col=default_ohlcv_col):
    """
    Add candlestick dimentions for dataframe

    :param df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :returns: dataframe with candlestick columns
    :raises: none
    """
    # copy dataframe
    df = df.copy()

    # set column names
    open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # candle color
    df['candle_color'] = 0
    up_idx = df[open] < df[close]
    down_idx = df[open] >= df[close]
    df.loc[up_idx, 'candle_color'] = 1
    df.loc[down_idx, 'candle_color'] = -1

    # shadow
    df['shadow'] = (df[high] - df[low])

    # entity
    df['entity'] = abs(df[close] - df[open])

    # ======================================= upper/lower shadow ======================================= #
    df['upper_shadow'] = 0
    df['lower_shadow'] = 0
    df.loc[up_idx, 'upper_shadow'] = (df.loc[up_idx, high] - df.loc[up_idx, close])
    df.loc[up_idx, 'lower_shadow'] = (df.loc[up_idx, open] - df.loc[up_idx, low])
    df.loc[down_idx, 'upper_shadow'] = (df.loc[down_idx, high] - df.loc[down_idx, open])
    df.loc[down_idx, 'lower_shadow'] = (df.loc[down_idx, close] - df.loc[down_idx, low])

    # gap_up / gap_down
    col_to_drop = []
    for col in [open, close, high, low, 'candle_color']:
        prev_col = f'prev_{col}'
        df[prev_col] = df[col].shift(1)
        col_to_drop.append(prev_col)

    # gap up
    df['gap'] = 0
    gap_up_idx = df.query(
        f'({low}>prev_{close} and prev_candle_color==1) or ({low}>prev_{open} and prev_candle_color==-1)').index
    strict_gap_up_idx = df.query(f'{low}>prev_{high}').index
    df.loc[gap_up_idx, 'gap'] = 1
    df.loc[strict_gap_up_idx, 'gap'] = 2

    # gap down
    gap_down_idx = df.query(
        f'({high}<prev_{open} and prev_candle_color==1) or ({high}<prev_{close} and prev_candle_color==-1)').index
    strict_gap_down_idx = df.query(f'{high}<prev_{low}').index
    df.loc[gap_down_idx, 'gap'] = -1
    df.loc[strict_gap_down_idx, 'gap'] = -2

    # ======================================= long entities ======================================= #
    df['long_entity'] = 0
    df['avg_entity_length'] = df['entity'].rolling(50).mean()
    long_entity_idx = df.query(f'(entity >= 3*avg_entity_length)').index
    df.loc[long_entity_idx, 'long_entity'] = df.loc[long_entity_idx, 'candle_color']
    col_to_drop.append('avg_entity_length')

    df['candlestick_signal'] = df['long_entity'].replace({0: 'n', 1: 'b', -1: 's'})

    df = df.drop(col_to_drop, axis=1)

    return df


# add heikin-ashi candlestick features
def add_heikin_ashi_features(df, ohlcv_col=default_ohlcv_col, replace_ohlc=False, dropna=True):
    """
    Add heikin-ashi candlestick dimentions for dataframe

    :param df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :returns: dataframe with candlestick columns
    :raises: none
    """
    # copy dataframe
    df = df.copy()

    # set column names
    open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # add previous stick
    for col in [open, high, low, close]:
        df[f'prev_{col}'] = df[col].shift(1)

    # calculate heikin-ashi ohlc
    df['H_Close'] = (df[open] + df[high] + df[low] + df[close]) / 4
    df['H_Open'] = (df[f'prev_{open}'] + df[f'prev_{close}']) / 2
    df['H_High'] = df[[f'prev_{high}', 'H_Open', 'H_Close']].max(axis=1)
    df['H_Low'] = df[[f'prev_{low}', 'H_Open', 'H_Close']].min(axis=1)

    # drop previous stick
    for col in [open, high, low, close]:
        df.drop(f'prev_{col}', axis=1, inplace=True)

    # replace original ohlc with heikin-ashi ohlc
    if replace_ohlc:
        for col in [open, high, low, close]:
            df.drop(f'{col}', axis=1, inplace=True)
        df.rename(columns={'H_Close': close, 'H_Open': open, 'H_High': high, 'H_Low': low}, inplace=True)

    # dropna values
    if dropna:
        df.dropna(inplace=True)

    return df


# ================================================ Trend indicators ================================================= #
# ADX(Average Directional Index)
def add_adx_features(df, n=14, ohlcv_col=default_ohlcv_col, fillna=False, adx_threshold=25):
    """
    Calculate ADX(Average Directional Index)

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param adx_threshold: the threshold to filter none-trending signals
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()
    # col_to_drop = []

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    # close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate true range
    df = add_atr_features(df=df, n=n, cal_signal=False)

    # difference of high/low between 2 continuouss days
    df['high_diff'] = df[high] - df[high].shift(1)
    df['low_diff'] = df[low].shift(1) - df[low]

    # plus/minus directional movements
    df['zero'] = 0
    df['pdm'] = df['high_diff'].combine(df['zero'], lambda x1, x2: get_min_max(x1, x2, 'max'))
    df['mdm'] = df['low_diff'].combine(df['zero'], lambda x1, x2: get_min_max(x1, x2, 'max'))

    # plus/minus directional indicators
    df['pdi'] = 100 * em(series=df['pdm'], periods=n).mean() / df['atr']
    df['mdi'] = 100 * em(series=df['mdm'], periods=n).mean() / df['atr']

    # directional movement index
    df['dx'] = 100 * abs(df['pdi'] - df['mdi']) / (df['pdi'] + df['mdi'])

    # Average directional index
    df['adx'] = em(series=df['dx'], periods=n).mean()

    idx = df.index.tolist()
    for i in range(n * 2, len(df) - 1):
        current_idx = idx[i]
        previous_idx = idx[i - 1]
        df.loc[current_idx, 'adx'] = (df.loc[previous_idx, 'adx'] * (n - 1) + df.loc[current_idx, 'dx']) / n

    # (pdi-mdi) / (adx/25)
    df['adx_diff'] = (df['pdi'] - df['mdi']) * (df['adx'] / adx_threshold)
    # df['adx_diff'] = (df['adx_diff'] - df['adx_diff'].mean()) / df['adx_diff'].std()

    # fill na values
    if fillna:
        for col in ['pdm', 'mdm', 'atr', 'pdi', 'mdi', 'dx', 'adx']:
            df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0)

    # drop redundant columns
    df.drop(['high_diff', 'low_diff', 'zero', 'pdm', 'mdm'], axis=1, inplace=True)

    return df


# Aroon
def add_aroon_features(df, n=25, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, boundary=[50, 50]):
    """
    Calculate Aroon

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param boundary: upper and lower boundary for calculating signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate aroon up and down indicators
    aroon_up = df[close].rolling(n, min_periods=0).apply(lambda x: float(np.argmax(x) + 1) / n * 100, raw=True)
    aroon_down = df[close].rolling(n, min_periods=0).apply(lambda x: float(np.argmin(x) + 1) / n * 100, raw=True)

    # fill na value with 0
    if fillna:
        aroon_up = aroon_up.replace([np.inf, -np.inf], np.nan).fillna(0)
        aroon_down = aroon_down.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign values to df
    df['aroon_up'] = aroon_up
    df['aroon_down'] = aroon_down

    # calculate gap between aroon_up and aroon_down
    df['aroon_gap'] = (df['aroon_up'] - df['aroon_down'])

    return df


# CCI(Commidity Channel Indicator)
def add_cci_features(df, n=20, c=0.015, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True,
                     boundary=[200, -200]):
    """
    Calculate CCI(Commidity Channel Indicator)

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param c: constant value used in cci calculation
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param boundary: upper and lower boundary for calculating signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate cci
    pp = (df[high] + df[low] + df[close]) / 3.0
    mad = lambda x: np.mean(np.abs(x - np.mean(x)))
    cci = (pp - pp.rolling(n, min_periods=0).mean()) / (c * pp.rolling(n).apply(mad, True))

    # assign values to dataframe
    df['cci'] = cci

    # calculate siganl
    df = cal_moving_average(df=df, target_col='cci', ma_windows=[3, 5])

    return df


# DPO(Detrended Price Oscillator)
def add_dpo_features(df, n=20, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate DPO(Detrended Price Oscillator)

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate dpo
    dpo = df[close].shift(int((0.5 * n) + 1)) - df[close].rolling(n, min_periods=0).mean()
    if fillna:
        dpo = dpo.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign values to df
    df['dpo'] = dpo

    # calculate_signal
    if cal_signal:
        df['zero'] = 0
        df['dpo_signal'] = cal_crossover_signal(df=df, fast_line='dpo', slow_line='zero')
        df.drop(labels='zero', axis=1, inplace=True)

    return df


# Ichimoku
def add_ichimoku_features(df, n_short=9, n_medium=26, n_long=52, method='ta', is_shift=True,
                          ohlcv_col=default_ohlcv_col, fillna=False, cal_status=True):
    """
    Calculate Ichimoku indicators

    :param df: original OHLCV dataframe
    :param n_short: short window size
    :param n_medium: medium window size
    :param n_long: long window size
    :param method: original/ta way to calculate ichimoku indicators
    :param is_shift: whether to shift senkou_a and senkou_b n_medium units
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated


    # signal: 在tankan平移, kijun向下的时候应该卖出; 在tankan向上, kijun向上或平移的时候应该买入
    """
    # copy dataframe
    df = df.copy()
    col_to_drop = []

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # use original method to calculate ichimoku indicators
    if method == 'original':
        df = cal_moving_average(df=df, target_col=high, ma_windows=[n_short, n_medium, n_long], window_type='sm')
        df = cal_moving_average(df=df, target_col=low, ma_windows=[n_short, n_medium, n_long], window_type='sm')

        # generate column names
        short_high = f'{high}_ma_{n_short}'
        short_low = f'{low}_ma_{n_short}'
        medium_high = f'{high}_ma_{n_medium}'
        medium_low = f'{low}_ma_{n_medium}'
        long_high = f'{high}_ma_{n_long}'
        long_low = f'{low}_ma_{n_long}'
        col_to_drop += [short_high, medium_high, long_high, short_low, medium_low, long_low]

        # calculate ichimoku indicators
        df['tankan'] = (df[short_high] + df[short_low]) / 2
        df['kijun'] = (df[medium_high] + df[medium_low]) / 2
        df['senkou_a'] = (df['tankan'] + df['kijun']) / 2
        df['senkou_b'] = (df[long_high] + df[long_low]) / 2
        df['chikan'] = df[close].shift(-n_medium)

    # use ta method to calculate ichimoku indicators
    elif method == 'ta':
        df['tankan'] = (df[high].rolling(n_short, min_periods=0).max() + df[low].rolling(n_short,
                                                                                         min_periods=0).min()) / 2
        df['kijun'] = (df[high].rolling(n_medium, min_periods=0).max() + df[low].rolling(n_medium,
                                                                                         min_periods=0).min()) / 2
        df['senkou_a'] = (df['tankan'] + df['kijun']) / 2
        df['senkou_b'] = (df[high].rolling(n_long, min_periods=0).max() + df[low].rolling(n_long,
                                                                                          min_periods=0).min()) / 2
        df['chikan'] = df[close].shift(-n_medium)

    # shift senkou_a and senkou_b n_medium units
    if is_shift:
        df['senkou_a'] = df['senkou_a'].shift(n_medium)
        df['senkou_b'] = df['senkou_b'].shift(n_medium)

    if cal_status:
        # ================================ Cloud status ===================================
        # cloud color change, cloud height (how thick is the cloud)
        df['cloud_shift'] = cal_crossover_signal(df=df, fast_line='senkou_a', slow_line='senkou_b', pos_signal=1,
                                                 neg_signal=-1, none_signal=0)
        df['cloud_height'] = round((df['senkou_a'] - df['senkou_b']) / df[close], ndigits=3)
        green_idx = df.query('cloud_height > 0').index
        red_idx = df.query('cloud_height <= 0').index

        # cloud width (how has it last)
        df['cloud_width'] = 0
        df.loc[green_idx, 'cloud_width'] = 1
        df.loc[red_idx, 'cloud_width'] = -1

        # cloud top and bottom
        df['cloud_top'] = 0
        df.loc[green_idx, 'cloud_top'] = df['senkou_a']
        df.loc[red_idx, 'cloud_top'] = df['senkou_b']
        df['cloud_bottom'] = 0
        df.loc[green_idx, 'cloud_bottom'] = df['senkou_b']
        df.loc[red_idx, 'cloud_bottom'] = df['senkou_a']

        # calculate how long current cloud has lasted
        idx = df.index.tolist()
        for i in range(1, len(df)):
            current_idx = idx[i]
            previous_idx = idx[i - 1]
            current_cloud_period = df.loc[current_idx, 'cloud_width']
            previous_cloud_period = df.loc[previous_idx, 'cloud_width']

            # calculate how long the cloud has last
            if current_cloud_period * previous_cloud_period > 0:
                df.loc[current_idx, 'cloud_width'] += previous_cloud_period

        # ================================ Close breakthrough =============================
        # calculate distance between Close and each ichimoku lines
        line_weight = {'kijun': 1, 'tankan': 1, 'cloud_top': 1, 'cloud_bottom': 1}
        line_name = {"kijun": "基准", "tankan": "转换", "cloud_top": "云顶", "cloud_bottom": "云底"}
        df['break_up'] = ''
        df['break_down'] = ''
        df['breakthrough'] = 0
        col_to_drop.append('breakthrough')

        for line in line_weight.keys():
            # set weight for this line
            weight = line_weight[line]

            # calculate breakthrough
            line_signal_name = f'{line}_signal'
            df[line_signal_name] = cal_crossover_signal(df=df, fast_line=close, slow_line=line, pos_signal=weight,
                                                        neg_signal=-weight, none_signal=0)

            # record breakthrough
            up_idx = df.query(f'{line_signal_name} == {weight}').index
            down_idx = df.query(f'{line_signal_name} == {-weight}').index
            df.loc[up_idx, 'break_up'] = df.loc[up_idx, 'break_up'] + line_name[line] + ','
            df.loc[down_idx, 'break_down'] = df.loc[down_idx, 'break_down'] + line_name[line] + ','

            # accumulate breakthrough signals
            df['breakthrough'] = df['breakthrough'].astype(int) + df[line_signal_name].astype(int)

            # calculate distance between close price and indicator
            df['close_to_' + line] = round((df[close] - df[line]) / df[close], ndigits=3)

        # drop redundant columns
        df.drop(col_to_drop, axis=1, inplace=True)

    return df


# KST(Know Sure Thing)
def add_kst_features(df, r1=10, r2=15, r3=20, r4=30, n1=10, n2=10, n3=10, n4=15, nsign=9, ohlcv_col=default_ohlcv_col,
                     fillna=False):
    """
    Calculate KST(Know Sure Thing)

    :param df: original OHLCV dataframe
    :param r_1: r1 window size
    :param r_2: r2 window size
    :param r_3: r3 window size
    :param r_4: r4 window size
    :param n_1: n1 window size
    :param n_2: n2 window size
    :param n_3: n3 window size
    :param n_4: n4 window size
    :param n_sign: kst signal window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()
    # col_to_drop = []

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate kst
    rocma1 = ((df[close] - df[close].shift(r1)) / df[close].shift(r1)).rolling(n1, min_periods=0).mean()
    rocma2 = ((df[close] - df[close].shift(r2)) / df[close].shift(r2)).rolling(n2, min_periods=0).mean()
    rocma3 = ((df[close] - df[close].shift(r3)) / df[close].shift(r3)).rolling(n3, min_periods=0).mean()
    rocma4 = ((df[close] - df[close].shift(r4)) / df[close].shift(r4)).rolling(n4, min_periods=0).mean()

    kst = 100 * (rocma1 + 2 * rocma2 + 3 * rocma3 + 4 * rocma4)
    kst_sign = kst.rolling(nsign, min_periods=0).mean()

    # fill na value
    if fillna:
        kst = kst.replace([np.inf, -np.inf], np.nan).fillna(0)
        kst_sign = kst_sign.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign values to df
    df['kst'] = kst
    df['kst_sign'] = kst_sign
    df['kst_diff'] = df['kst'] - df['kst_sign']
    df['kst_diff'] = (df['kst_diff'] - df['kst_diff'].mean()) / df['kst_diff'].std()

    return df


# MACD(Moving Average Convergence Divergence)
def add_macd_features(df, n_fast=12, n_slow=26, n_sign=9, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate MACD(Moving Average Convergence Divergence)

    :param df: original OHLCV dataframe
    :param n_fast: ma window of fast ma
    :param n_slow: ma window of slow ma
    :paran n_sign: ma window of macd signal line
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate fast and slow ema of close price
    emafast = em(series=df[close], periods=n_fast, fillna=fillna).mean()
    emaslow = em(series=df[close], periods=n_slow, fillna=fillna).mean()

    # calculate macd, ema(macd), macd-ema(macd)
    macd = emafast - emaslow
    macd_sign = em(series=macd, periods=n_sign, fillna=fillna).mean()
    macd_diff = macd - macd_sign

    # fill na value with 0
    if fillna:
        macd = macd.replace([np.inf, -np.inf], np.nan).fillna(0)
        macd_sign = macd_sign.replace([np.inf, -np.inf], np.nan).fillna(0)
        macd_diff = macd_diff.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign valuse to df
    df['macd'] = macd
    df['macd_sign'] = macd_sign
    df['macd_diff'] = macd_diff

    # calculate crossover signal
    if cal_signal:
        df['zero'] = 0
        df['macd_signal'] = cal_crossover_signal(df=df, fast_line='macd_diff', slow_line='zero')
        df.drop(labels='zero', axis=1, inplace=True)

    return df


# Mass Index
def add_mi_features(df, n=9, n2=25, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Mass Index

    :param df: original OHLCV dataframe
    :param n: ema window of high-low difference
    :param n_2: window of cumsum of ema ratio
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    # close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    amplitude = df[high] - df[low]
    ema1 = em(series=amplitude, periods=n, fillna=fillna).mean()
    ema2 = em(series=ema1, periods=n, fillna=fillna).mean()
    mass = ema1 / ema2
    mass = mass.rolling(n2, min_periods=0).sum()

    # fillna value
    if fillna:
        mass = mass.replace([np.inf, -np.inf], np.nan).fillna(n2)

    # assign value to df
    df['mi'] = mass

    # calculate signal
    if cal_signal:
        df['benchmark'] = 27
        df['triger_signal'] = cal_crossover_signal(df=df, fast_line='mi', slow_line='benchmark', pos_signal='b',
                                                   neg_signal='n', none_signal='n')
        df['benchmark'] = 26.5
        df['complete_signal'] = cal_crossover_signal(df=df, fast_line='mi', slow_line='benchmark', pos_signal='n',
                                                     neg_signal='s', none_signal='n')

        up_idx = df.query('triger_signal == "b"').index
        down_idx = df.query('complete_signal == "s"').index
        df['mi_signal'] = 'n'
        df.loc[up_idx, 'mi_signal'] = 'b'
        df.loc[down_idx, 'mi_signal'] = 's'

        df.drop(['benchmark', 'triger_signal', 'complete_signal'], axis=1, inplace=True)

    return df


# TRIX
def add_trix_features(df, n=15, n_sign=9, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True,
                      signal_mode='mix'):
    """
    Calculate TRIX

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param n_sign: ema window of signal line (ema of trix)
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate trix
    ema1 = em(series=df[close], periods=n, fillna=fillna).mean()
    ema2 = em(series=ema1, periods=n, fillna=fillna).mean()
    ema3 = em(series=ema2, periods=n, fillna=fillna).mean()
    trix = (ema3 - ema3.shift(1)) / ema3.shift(1)
    trix *= 100

    # fillna value
    if fillna:
        trix = trix.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign value to df
    df['trix'] = trix
    df['trix_sign'] = em(series=trix, periods=n_sign, fillna=fillna).mean()
    df['trix_diff'] = df['trix'] - df['trix_sign']

    return df


# Vortex
def add_vortex_features(df, n=14, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Vortex indicator

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate vortex
    tr = (df[high].combine(df[close].shift(1), max) - df[low].combine(df[close].shift(1), min))
    trn = tr.rolling(n).sum()

    vmp = np.abs(df[high] - df[low].shift(1))
    vmm = np.abs(df[low] - df[high].shift(1))

    vip = vmp.rolling(n, min_periods=0).sum() / trn
    vin = vmm.rolling(n, min_periods=0).sum() / trn

    if fillna:
        vip = vip.replace([np.inf, -np.inf], np.nan).fillna(1)
        vin = vin.replace([np.inf, -np.inf], np.nan).fillna(1)

    # assign values to df
    df['vortex_pos'] = vip
    df['vortex_neg'] = vin
    df['vortex_diff'] = df['vortex_pos'] - df['vortex_neg']
    df['vortex_diff'] = df['vortex_diff'] - df['vortex_diff'].shift(1)

    # calculate signal
    if cal_signal:
        df['vortex_signal'] = cal_crossover_signal(df=df, fast_line='vortex_pos', slow_line='vortex_neg')

    return df


# PSAR
def add_psar_features(df, ohlcv_col=default_ohlcv_col, step=0.02, max_step=0.10, fillna=False, cal_signal=True):
    """
    Calculate Parabolic Stop and Reverse (Parabolic SAR) indicator

    :param df: original OHLCV dataframe
    :param step: unit of a step
    :param max_step: up-limit of step
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    df['psar'] = df[close].copy()
    df['psar_up'] = np.NaN
    df['psar_down'] = np.NaN

    up_trend = True
    af = step
    idx = df.index.tolist()
    up_trend_high = df.loc[idx[0], high]
    down_trend_low = df.loc[idx[0], low]

    for i in range(2, len(df)):
        current_idx = idx[i]
        previous_idx = idx[i - 1]
        previous_previous_idx = idx[i - 2]

        reversal = False
        max_high = df.loc[current_idx, high]
        min_low = df.loc[current_idx, low]

        if up_trend:
            df.loc[current_idx, 'psar'] = df.loc[previous_idx, 'psar'] + (
                    af * (up_trend_high - df.loc[previous_idx, 'psar']))

            if min_low < df.loc[current_idx, 'psar']:
                reversal = True
                df.loc[current_idx, 'psar'] = up_trend_high
                down_trend_low = min_low
                af = step
            else:
                if max_high > up_trend_high:
                    up_trend_high = max_high
                    af = min(af + step, max_step)

                l1 = df.loc[previous_idx, low]
                l2 = df.loc[previous_previous_idx, low]
                if l2 < df.loc[current_idx, 'psar']:
                    df.loc[current_idx, 'psar'] = l2
                elif l1 < df.loc[current_idx, 'psar']:
                    df.loc[current_idx, 'psar'] = l1

        else:
            df.loc[current_idx, 'psar'] = df.loc[previous_idx, 'psar'] - (
                    af * (df.loc[previous_idx, 'psar'] - down_trend_low))

            if max_high > df.loc[current_idx, 'psar']:
                reversal = True
                df.loc[current_idx, 'psar'] = down_trend_low
                up_trend_high = max_high
                af = step
            else:
                if min_low < down_trend_low:
                    down_trend_low = min_low
                    af = min(af + step, max_step)

                h1 = df.loc[previous_idx, high]
                h2 = df.loc[previous_previous_idx, high]
                if h2 > df.loc[current_idx, 'psar']:
                    df.loc[current_idx, 'psar'] = h2
                elif h1 > df.loc[current_idx, 'psar']:
                    df.loc[current_idx, 'psar'] = h1

        up_trend = (up_trend != reversal)

        if up_trend:
            df.loc[current_idx, 'psar_up'] = df.loc[current_idx, 'psar']
        else:
            df.loc[current_idx, 'psar_down'] = df.loc[current_idx, 'psar']

    # add psar up/down indicators
    for col in ['psar_up', 'psar_down']:
        indicator = df[col].where(df[col].notnull() & df[col].shift(1).isnull(), 0)
        indicator = indicator.where(indicator == 0, 1)
        df[f'{col}_indicator'] = indicator

    # fill na values
    if fillna:
        for col in ['psar', 'psar_up', 'psar_down', 'psar_up_indicator', 'psar_down_indicator']:
            df[col] = df[col].fillna(method='ffill').fillna(-1)

    if cal_signal:
        df['psar_signal'] = 'n'

    return df


# Renko
def add_renko_features(df, brick_size=None, use_atr=True, return_date_index=True, cal_signal=True):
    """
    Calculate Renko indicator

    :param df: original OHLCV dataframe
    :param brick_size: brick size, default is 1/3 of close.std
    :param use_atr: whether to use the latest atr vaule as the brick size
    :param return_date_index: whether to remove duplicated indexes from the final result
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """

    # reset index and copy df
    original_df = remove_duplicated_index(df=df, keep='last')
    df = original_df.reset_index()

    # set brick size
    if use_atr:
        df = add_atr_features(df=df)
        brick_size = df['atr'].values[-1]
    elif not use_atr and brick_size is None:
        # brick_size = df['Close'].std()/4
        brick_size = df['Close'].mean() / 10

    # construct dataframe
    columns = ['Date', 'Open', 'High', 'Low', 'Close']
    cdf = pd.DataFrame(columns=columns, data=[], )

    # set the first row
    cdf.loc[0] = df.loc[0]
    close = df.loc[0]['Close'] // brick_size * brick_size
    cdf.loc[0, 1:] = [close - brick_size, close, close - brick_size, close]
    cdf['uptrend'] = True
    columns = ['Date', 'Open', 'High', 'Low', 'Close', 'uptrend']

    # go through the dataframe
    for index, row in df.iterrows():

        # get current date and close price
        close = row['Close']
        date = row['Date']

        # get previous row
        row_p1 = cdf.iloc[-1]
        uptrend = row_p1['uptrend']
        close_p1 = row_p1['Close']

        # calculate bricks
        bricks = int((close - close_p1) / brick_size)
        data = []

        # if in a uptrend and close_diff is larger than 1 brick
        if uptrend and bricks >= 1:
            for i in range(bricks):
                r = [date, close_p1, close_p1 + brick_size, close_p1, close_p1 + brick_size, uptrend]
                data.append(r)
                close_p1 += brick_size
        # if in a uptrend and closs_diff is larger than 2 bricks(in a negative way)
        elif uptrend and bricks <= -2:
            uptrend = not uptrend
            bricks += 1
            close_p1 -= brick_size
            for i in range(abs(bricks)):
                r = [date, close_p1, close_p1, close_p1 - brick_size, close_p1 - brick_size, uptrend]
                data.append(r)
                close_p1 -= brick_size
        # if in a downtrend and close_diff is larger than 1 brick(in a negative way)
        elif not uptrend and bricks <= -1:
            for i in range(abs(bricks)):
                r = [date, close_p1, close_p1, close_p1 - brick_size, close_p1 - brick_size, uptrend]
                data.append(r)
                close_p1 -= brick_size
        # if in a downtrend and close_diff is larger than 2 bricks
        elif not uptrend and bricks >= 2:
            uptrend = not uptrend
            bricks -= 1
            close_p1 += brick_size
            for i in range(abs(bricks)):
                r = [date, close_p1, close_p1 + brick_size, close_p1, close_p1 + brick_size, uptrend]
                data.append(r)
                close_p1 += brick_size
        else:
            continue

        # construct the [1:] rows and attach it to the first row
        sdf = pd.DataFrame(data=data, columns=columns)
        cdf = pd.concat([cdf, sdf])

    # post process
    cdf = df_2_timeseries(df=cdf, time_col='Date')
    cdf.rename(columns={'Open': 'renko_o', 'High': 'renko_h', 'High': 'renko_h', 'Low': 'renko_l', 'Close': 'renko_c',
                        'uptrend': 'renko_color'}, inplace=True)
    cdf['renko_color'] = cdf['renko_color'].replace({True: 'green', False: 'red'})
    cdf['renko_real'] = cdf['renko_color'].copy()
    cdf['renko_trend'] = cdf['renko_color'].replace({'green': 'u', 'red': 'd'})
    cdf['renko_sda'] = cdf['renko_color'].replace({'green': 1, 'red': -1})
    cdf['renko_sda'] = sda(series=cdf['renko_sda'], zero_as=0)
    cdf['renko_brick_size'] = brick_size

    # merge cdf with original df
    for col in ['renko_o', 'renko_h', 'renko_l', 'renko_c', 'renko_color', 'renko_trend', 'renko_real', 'renko_sda',
                'renko_brick_size']:
        if col in original_df.columns:
            original_df.drop(col, axis=1, inplace=True)
    original_df = pd.merge(original_df, cdf, how='left', left_index=True, right_index=True)
    # original_df['renko_trend'] = original_df['renko_color'].replace({'green':'u', 'red':'d'})
    # original_df['renko_real'] = original_df['renko_color'].copy()

    # if to return date index
    if return_date_index:
        duplicated_idx = list(set(original_df.index[original_df.index.duplicated()]))

        # remove duplicated date index
        for idx in duplicated_idx:
            tmp_rows = original_df.loc[idx,].copy()

            # make sure they are in same color
            colors = tmp_rows['renko_color'].unique()
            if len(colors) == 1:
                color = colors[0]
                if color == 'green':
                    original_df.loc[idx, 'renko_o'] = tmp_rows['renko_o'].min()
                    original_df.loc[idx, 'renko_l'] = tmp_rows['renko_l'].min()
                    original_df.loc[idx, 'renko_h'] = tmp_rows['renko_h'].max()
                    original_df.loc[idx, 'renko_c'] = tmp_rows['renko_c'].max()
                    original_df.loc[idx, 'renko_brick_size'] = tmp_rows['renko_brick_size'].sum()
                elif color == 'red':
                    original_df.loc[idx, 'renko_o'] = tmp_rows['renko_o'].max()
                    original_df.loc[idx, 'renko_l'] = tmp_rows['renko_l'].min()
                    original_df.loc[idx, 'renko_h'] = tmp_rows['renko_h'].max()
                    original_df.loc[idx, 'renko_c'] = tmp_rows['renko_c'].min()
                    original_df.loc[idx, 'renko_brick_size'] = tmp_rows['renko_brick_size'].sum()
                else:
                    print(f'unknown renko color {color}')
                    continue
            else:
                print('duplicated index with different renko colors!')
                continue
        original_df = remove_duplicated_index(df=original_df, keep='last')

    # change the value of downtrend bricks
    red_idx = original_df.query('renko_color == "red"').index
    original_df.loc[red_idx, 'renko_brick_size'] = -original_df.loc[red_idx, 'renko_brick_size']

    # fill na values
    original_df[
        ['renko_o', 'renko_h', 'renko_l', 'renko_c', 'renko_color', 'renko_brick_size', 'renko_trend', 'renko_sda']] = \
        original_df[['renko_o', 'renko_h', 'renko_l', 'renko_c', 'renko_color', 'renko_brick_size', 'renko_trend',
                     'renko_sda']].fillna(method='ffill')

    # calculate signals
    if cal_signal:
        original_df['renko_signal'] = original_df['renko_real'].replace({'green': 'b', 'red': 's'})

        # # calculate sda of bricks
        # original_df['renko_sda'] = original_df['renko_real'].replace({'green':1, 'red':-1}).fillna(0)
        # original_df['renko_sda'] = sda(series = original_df['renko_sda'], zero_as=0)

    return original_df


# ================================================ Volume indicators ================================================ #
# Accumulation Distribution Index
def add_adi_features(df, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Accumulation Distribution Index

    :param df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """

    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate ADI
    clv = ((df[close] - df[low]) - (df[high] - df[close])) / (df[high] - df[low])
    clv = clv.fillna(0.0)  # float division by zero
    ad = clv * df[volume]
    ad = ad + ad.shift(1)

    # fill na values
    if fillna:
        ad = ad.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign adi to df
    df['adi'] = ad

    # calculate signals
    if cal_signal:
        df['adi_signal'] = 'n'

    return df


# *Chaikin Money Flow (CMF)
def add_cmf_features(df, n=20, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Chaikin Money FLow

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """

    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate cmf
    mfv = ((df[close] - df[low]) - (df[high] - df[close])) / (df[high] - df[low])
    mfv = mfv.fillna(0.0)  # float division by zero
    mfv *= df[volume]
    cmf = (mfv.rolling(n, min_periods=0).sum() / df[volume].rolling(n, min_periods=0).sum())

    # fill na values
    if fillna:
        cmf = cmf.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign cmf to df
    df['cmf'] = cmf

    # calculate signals
    if cal_signal:
        df['cmf_signal'] = cal_boundary_signal(df=df, upper_col='cmf', lower_col='cmf', upper_boundary=0.05,
                                               lower_boundary=-0.05)

    return df


# Ease of movement (EoM, EMV)
def add_eom_features(df, n=20, ohlcv_col=default_ohlcv_col, fillna=False):
    """
    Calculate Vortex indicator

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """

    # copy dataframe
    df = df.copy()
    # col_to_drop = []

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    # close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate eom
    eom = (df[high].diff(periods=1) + df[low].diff(periods=1)) * (df[high] - df[low]) / (df[volume] * 2)
    eom = eom.rolling(window=n, min_periods=0).mean()

    # fill na values
    if fillna:
        eom = eom.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign eom to df
    df['eom'] = eom

    # calculate eom_ma_14 and eom - eom_ma_14
    df = cal_moving_average(df=df, target_col='eom', ma_windows=[14], window_type='sm')
    df['eom_diff'] = df['eom'] - df['eom_ma_14']
    df['eom_diff'] = (df['eom_diff'] - df['eom_diff'].mean()) / df['eom_diff'].std()

    return df


# Force Index (FI)
def add_fi_features(df, n1=2, n2=22, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Force Index

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """

    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate fi
    fi = df[close].diff(n1) * df[volume]  # .diff(n)
    fi_ema = em(series=fi, periods=n2).mean()

    # fill na values
    if fillna:
        fi = fi.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign fi to df
    df['fi'] = fi
    df['fi_ema'] = fi_ema

    # calculate signals
    if cal_signal:
        df['fi_signal'] = 'n'

    return df


# *Negative Volume Index (NVI)
def add_nvi_features(df, n=255, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Negative Volume Index (NVI)

    :param df: original OHLCV dataframe
    :param n: ema window of close price
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate nvi
    price_change = df[close].pct_change() * 100
    vol_decress = (df[volume].shift(1) > df[volume])

    nvi = pd.Series(data=np.nan, index=df[close].index, dtype='float64', name='nvi')

    nvi.iloc[0] = 1000
    for i in range(1, len(nvi)):
        if vol_decress.iloc[i]:
            nvi.iloc[i] = nvi.iloc[i - 1] + (price_change.iloc[i])
        else:
            nvi.iloc[i] = nvi.iloc[i - 1]

    # fill na values
    if fillna:
        nvi = nvi.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign nvi to df
    df['nvi'] = nvi
    df['nvi_ema'] = em(series=nvi, periods=n).mean()

    # calculate signal
    if cal_signal:
        df['nvi_signal'] = 'n'

    return df


# *On-balance volume (OBV)
def add_obv_features(df, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Force Index

    :param df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate obv
    df['OBV'] = np.nan
    c1 = df[close] < df[close].shift(1)
    c2 = df[close] > df[close].shift(1)
    if c1.any():
        df.loc[c1, 'OBV'] = - df[volume]
    if c2.any():
        df.loc[c2, 'OBV'] = df[volume]
    obv = df['OBV'].cumsum()
    obv = obv.fillna(method='ffill')

    # fill na values
    if fillna:
        obv = obv.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign obv to df
    df['obv'] = obv

    df.drop('OBV', axis=1, inplace=True)
    return df


# *Volume-price trend (VPT)
def add_vpt_features(df, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Vortex indicator

    :param df: original OHLCV dataframe
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate vpt
    df['close_change_rate'] = df[close].pct_change(periods=1)
    vpt = df[volume] * df['close_change_rate']
    vpt = vpt.shift(1) + vpt

    # fillna values
    if fillna:
        vpt = vpt.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign vpt value to df
    df['vpt'] = vpt

    # calculate signals
    if cal_signal:
        df['vpt_signal'] = 'n'

    # drop redundant columns
    df.drop(['close_change_rate'], axis=1, inplace=True)

    return df


# ================================================ Momentum indicators ============================================== #
# Awesome Oscillator
def add_ao_features(df, n_short=5, n_long=34, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Awesome Oscillator

    :param df: original OHLCV dataframe
    :param n_short: short window size for calculating sma
    :param n_long: long window size for calculating sma
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    # close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate ao
    mp = 0.5 * (df[high] + df[low])
    ao = mp.rolling(n_short, min_periods=0).mean() - mp.rolling(n_long, min_periods=0).mean()

    # fill na values
    if fillna:
        ao = ao.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign ao to df
    df['ao'] = ao
    df['ao_diff'] = df['ao'] - df['ao'].shift(1)

    return df


# Kaufman's Adaptive Moving Average (KAMA)
def cal_kama(df, n1=10, n2=2, n3=30, ohlcv_col=default_ohlcv_col, fillna=False):
    """
    Calculate Kaufman's Adaptive Moving Average

    :param df: original OHLCV dataframe
    :param n1: number of periods for Efficiency Ratio(ER)
    :param n2: number of periods for the fastest EMA constant
    :param n3: number of periods for the slowest EMA constant
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate kama
    close_values = df[close].values
    vol = pd.Series(abs(df[close] - np.roll(df[close], 1)))

    ER_num = abs(close_values - np.roll(close_values, n1))
    ER_den = vol.rolling(n1).sum()
    ER = ER_num / ER_den

    sc = ((ER * (2.0 / (n2 + 1.0) - 2.0 / (n3 + 1.0)) + 2.0 / (n3 + 1.0)) ** 2.0).values

    kama = np.zeros(sc.size)
    N = len(kama)
    first_value = True

    for i in range(N):
        if np.isnan(sc[i]):
            kama[i] = np.nan
        else:
            if first_value:
                kama[i] = close_values[i]
                first_value = False
            else:
                kama[i] = kama[i - 1] + sc[i] * (close_values[i] - kama[i - 1])

    kama = pd.Series(kama, name='kama', index=df[close].index)

    # fill na values
    if fillna:
        kama = kama.replace([np.inf, -np.inf], np.nan).fillna(df[close])

    # assign kama to df
    df['kama'] = kama

    return df


# Kaufman's Adaptive Moving Average (KAMA)
def add_kama_features(df, n_param={'kama_fast': [10, 2, 30], 'kama_slow': [10, 5, 30]}, ohlcv_col=default_ohlcv_col,
                      fillna=False):
    """
    Calculate Kaufman's Adaptive Moving Average Signal

    :param df: original OHLCV dataframe
    :param n_param: series of n parameters fro calculating kama in different periods
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate fast and slow kama
    for k in n_param.keys():
        tmp_n = n_param[k]
        if len(tmp_n) != 3:
            print(k, ' please provide all 3 parameters')
            continue
        else:
            n1 = tmp_n[0]
            n2 = tmp_n[1]
            n3 = tmp_n[2]
            df = cal_kama(df=df, n1=n1, n2=n2, n3=n3, ohlcv_col=ohlcv_col)
            df.rename(columns={'kama': k}, inplace=True)

    # calculate distance between close price and indicator
    kama_lines = ['kama_fast', 'kama_slow']
    for line in kama_lines:
        df[f'close_to_{line}'] = round((df[close] - df[line]) / df[close], ndigits=3)
        df[f'{line}_signal'] = cal_crossover_signal(df=df, fast_line=close, slow_line=line, pos_signal=1, neg_signal=-1,
                                                    none_signal=0)

    return df


# Money Flow Index(MFI)
def add_mfi_features(df, n=14, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, boundary=[20, 80]):
    """
    Calculate Money Flow Index Signal

    :param df: original OHLCV dataframe
    :param n: ma window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param boundary: boundaries for overbuy/oversell
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    volume = ohlcv_col['volume']

    # calculate adi
    typical_price = (df[high] + df[low] + df[close]) / 3.0

    df['up_or_down'] = 0
    df.loc[(typical_price > typical_price.shift(1)), 'up_or_down'] = 1
    df.loc[(typical_price < typical_price.shift(1)), 'up_or_down'] = -1

    money_flow = typical_price * df[volume] * df['up_or_down']

    n_positive_mf = money_flow.rolling(n).apply(
        lambda x: np.sum(np.where(x >= 0.0, x, 0.0)),
        raw=True)

    n_negative_mf = abs(money_flow.rolling(n).apply(
        lambda x: np.sum(np.where(x < 0.0, x, 0.0)),
        raw=True))

    mfi = n_positive_mf / n_negative_mf
    mfi = (100 - (100 / (1 + mfi)))

    # fill na values, as 50 is the central line (mfi wave between 0-100)
    if fillna:
        mfi = mfi.replace([np.inf, -np.inf], np.nan).fillna(50)

    # assign mfi to df
    df['mfi'] = mfi

    # calculate signals
    if cal_signal:
        df['mfi_signal'] = cal_boundary_signal(df=df, upper_col='mfi', lower_col='mfi', upper_boundary=max(boundary),
                                               lower_boundary=min(boundary))
        df = remove_redundant_signal(df=df, signal_col='mfi_signal', pos_signal='s', neg_signal='b', none_signal='n',
                                     keep='first')

    df.drop('up_or_down', axis=1, inplace=True)
    return df


# Relative Strength Index (RSI)
def add_rsi_features(df, n=14, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, boundary=[30, 70]):
    """
    Calculate Relative Strength Index

    :param df: original OHLCV dataframe
    :param n: ma window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param boundary: boundaries for overbuy/oversell
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate RSI
    diff = df[close].pct_change(1)

    up = diff.copy()
    up[diff < 0] = 0

    down = -diff.copy()
    down[diff > 0] = 0

    emaup = up.ewm(com=n - 1, min_periods=0).mean()
    emadown = down.ewm(com=n - 1, min_periods=0).mean()

    rsi = 100 * emaup / (emaup + emadown)

    # fill na values, as 50 is the central line (rsi wave between 0-100)
    if fillna:
        rsi = rsi.replace([np.inf, -np.inf], np.nan).fillna(50)

    # assign rsi to df
    df['rsi'] = rsi

    # calculate signals
    if cal_signal:
        df['rsi_signal'] = cal_boundary_signal(df=df, upper_col='rsi', lower_col='rsi', upper_boundary=max(boundary),
                                               lower_boundary=min(boundary), pos_signal='s', neg_signal='b',
                                               none_signal='n')
        df = remove_redundant_signal(df=df, signal_col='rsi_signal', pos_signal='s', neg_signal='b', none_signal='n',
                                     keep='first')

    return df


# Stochastic Oscillator
def add_stoch_features(df, n=14, d_n=3, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, boundary=[20, 80]):
    """
    Calculate Stochastic Oscillator

    :param df: original OHLCV dataframe
    :param n: ma window size
    :param d_n: ma window size for stoch
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :param boundary: boundaries for overbuy/oversell
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate stochastic
    stoch_min = df[low].rolling(n, min_periods=0).min()
    stoch_max = df[high].rolling(n, min_periods=0).max()
    stoch_k = 100 * (df[close] - stoch_min) / (stoch_max - stoch_min)
    stoch_d = stoch_k.rolling(d_n, min_periods=0).mean()

    # fill na values, as 50 is the central line (rsi wave between 0-100)
    if fillna:
        stoch_k = stoch_k.replace([np.inf, -np.inf], np.nan).fillna(50)
        stoch_d = stoch_d.replace([np.inf, -np.inf], np.nan).fillna(50)

    # assign stochastic values to df
    df['stoch_k'] = stoch_k
    df['stoch_d'] = stoch_d
    df['stoch_diff'] = df['stoch_k'] - df['stoch_d']
    df['stoch_diff'] = df['stoch_diff'] - df['stoch_diff'].shift(1)

    return df


# True strength index (TSI)
def add_tsi_features(df, r=25, s=13, ema_period=7, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate True strength index

    :param df: original OHLCV dataframe
    :param r: ma window size for high
    :param s: ma window size for low
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate tsi
    m = df[close] - df[close].shift(1, fill_value=df[close].mean())
    m1 = m.ewm(r).mean().ewm(s).mean()
    m2 = abs(m).ewm(r).mean().ewm(s).mean()
    tsi = 100 * (m1 / m2)
    tsi_sig = em(series=tsi, periods=ema_period).mean()

    # fill na values
    if fillna:
        tsi = tsi.replace([np.inf, -np.inf], np.nan).fillna(0)
        tsi_sig = tsi_sig.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign tsi to df
    df['tsi'] = tsi
    df['tsi_sig'] = tsi_sig

    # calculate signal
    if cal_signal:
        df['zero'] = 0
        df['tsi_fast_slow_signal'] = cal_crossover_signal(df=df, fast_line='tsi', slow_line='tsi_sig',
                                                          result_col='signal', pos_signal='b', neg_signal='s',
                                                          none_signal='n')
        df['tsi_centerline_signal'] = cal_crossover_signal(df=df, fast_line='tsi', slow_line='zero',
                                                           result_col='signal', pos_signal='b', neg_signal='s',
                                                           none_signal='n')

    return df


# Ultimate Oscillator
def add_uo_features(df, s=7, m=14, l=28, ws=4.0, wm=2.0, wl=1.0, ohlcv_col=default_ohlcv_col, fillna=False,
                    cal_signal=False):
    """
    Calculate Ultimate Oscillator

    :param df: original OHLCV dataframe
    :param s: short ma window size
    :param m: mediem window size
    :param l: long window size
    :param ws: weight for short period
    :param wm: weight for medium period
    :param wl: weight for long period
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate uo
    min_l_or_pc = df[close].shift(1, fill_value=df[close].mean()).combine(df[low], min)
    max_h_or_pc = df[close].shift(1, fill_value=df[close].mean()).combine(df[high], max)

    bp = df[close] - min_l_or_pc
    tr = max_h_or_pc - min_l_or_pc

    avg_s = bp.rolling(s, min_periods=0).sum() / tr.rolling(s, min_periods=0).sum()
    avg_m = bp.rolling(m, min_periods=0).sum() / tr.rolling(m, min_periods=0).sum()
    avg_l = bp.rolling(l, min_periods=0).sum() / tr.rolling(l, min_periods=0).sum()

    uo = 100.0 * ((ws * avg_s) + (wm * avg_m) + (wl * avg_l)) / (ws + wm + wl)

    # fill na values
    if fillna:
        uo = uo.replace([np.inf, -np.inf], np.nan).fillna(0)

    # assign uo to df
    df['uo'] = uo
    df['uo_diff'] = df['uo'] - df['uo'].shift(1)

    return df


# Williams %R
def add_wr_features(df, lbp=14, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, boundary=[-20, -80]):
    """
    Calculate Williams %R

    :param df: original OHLCV dataframe
    :param lbp: look back period
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate wr
    hh = df[high].rolling(lbp, min_periods=0).max()
    ll = df[low].rolling(lbp, min_periods=0).min()

    wr = -100 * (hh - df[close]) / (hh - ll)

    # fill na values
    if fillna:
        wr = wr.replace([np.inf, -np.inf], np.nan).fillna(-50)

    # assign wr to df
    df['wr'] = wr

    # calulate signal
    if cal_signal:
        df['wr_signal'] = cal_boundary_signal(df=df, upper_col='wr', lower_col='wr', upper_boundary=max(boundary),
                                              lower_boundary=min(boundary))

    return df


# ================================================ Volatility indicators ============================================ #
# Average True Range
def add_atr_features(df, n=14, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Average True Range

    :param df: original OHLCV dataframe
    :param n: ema window
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate true range
    df['h_l'] = df[low] - df[low]
    df['h_pc'] = abs(df[high] - df[close].shift(1))
    df['l_pc'] = abs(df[low] - df[close].shift(1))
    df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis=1)

    # calculate average true range
    df['atr'] = sm(series=df['tr'], periods=n, fillna=True).mean()

    idx = df.index.tolist()
    for i in range(n, len(df)):
        current_idx = idx[i]
        previous_idx = idx[i - 1]
        df.loc[current_idx, 'atr'] = (df.loc[previous_idx, 'atr'] * 13 + df.loc[current_idx, 'tr']) / 14

    # fill na value
    if fillna:
        df['atr'] = df['atr'].replace([np.inf, -np.inf], np.nan).fillna(0)

    # calculate signal
    if cal_signal:
        df['atr_signal'] = df['tr'] - df['atr']

    df.drop(['h_l', 'h_pc', 'l_pc'], axis=1, inplace=True)

    return df


# Mean Reversion
# def add_mean_reversion_features(df, n=100, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True, mr_threshold=2):
#     """
#     Calculate Mean Reversion
#
#     :param df: original OHLCV dataframe
#     :param n: look back window size
#     :param ohlcv_col: column name of Open/High/Low/Close/Volume
#     :param fillna: whether to fill na with 0
#     :param cal_signal: whether to calculate signal
#     :param mr_threshold: the threshold to triger signal
#     :returns: dataframe with new features generated
#     """
#     # copy dataframe
#     df = df.copy()
#
#     # set column names
#     # open = ohlcv_col['open']
#     # high = ohlcv_col['high']
#     # low = ohlcv_col['low']
#     close = ohlcv_col['close']
#     # volume = ohlcv_col['volume']
#
#     # calculate change rate of close price
#     df = cal_change_rate(df=df, target_col=close, periods=1, add_accumulation=True)
#     target_col = ['rate', 'acc_rate', 'acc_day']
#
#     # calculate the (current value - moving avg) / moving std
#     for col in target_col:
#         mw = sm(series=df[col], periods=n)
#         tmp_mean = mw.mean()
#         tmp_std = mw.std()
#         df[col + '_bias'] = (df[col] - tmp_mean) / (tmp_std)
#
#     # calculate the expected change rate that will triger signal
#     result = cal_mean_reversion_expected_rate(df=df, rate_col='acc_rate', n=n, mr_threshold=mr_threshold)
#     last_acc_rate = df['acc_rate'].tail(1).values[0]
#     last_close = df[close].tail(1).values[0]
#
#     up = down = 0
#     if last_acc_rate > 0:
#         up = max(result) - last_acc_rate
#         down = min(result)
#     else:
#         up = max(result)
#         down = min(result) - last_acc_rate
#
#     up_price = round((1 + up) * last_close, ndigits=2)
#     down_price = round((1 + down) * last_close, ndigits=2)
#     up = round(up * 100, ndigits=0)
#     down = round(down * 100, ndigits=0)
#     df['mr_price'] = f'{up_price}({up}%%),{down_price}({down}%%)'
#
#     # calculate mr signal
#     if cal_signal:
#         df['rate_signal'] = cal_boundary_signal(df=df, upper_col='rate_bias', lower_col='rate_bias',
#                                                 upper_boundary=mr_threshold, lower_boundary=-mr_threshold, pos_signal=1,
#                                                 neg_signal=-1, none_signal=0)
#         df['acc_rate_signal'] = cal_boundary_signal(df=df, upper_col='acc_rate_bias', lower_col='acc_rate_bias',
#                                                     upper_boundary=mr_threshold, lower_boundary=-mr_threshold,
#                                                     pos_signal=1, neg_signal=-1, none_signal=0)
#         df['mr_signal'] = df['rate_signal'].astype(int) + df['acc_rate_signal'].astype(int)
#         df = replace_signal(df=df, signal_col='mr_signal', replacement={0: 'n', 1: 'n', -1: 'n', 2: 'b', -2: 's'})
#         df.drop(['rate_signal', 'acc_rate_signal'], axis=1, inplace=True)
#
#     return df


# Price that will triger mean reversion signal
# def cal_mean_reversion_expected_rate(df, rate_col, n=100, mr_threshold=2):
#     """
#     Calculate the expected rate change to triger mean-reversion signals
#
#     :param df: original dataframe which contains rate column
#     :param rate_col: columnname of the change rate values
#     :param n: windowsize of the moving window
#     :param mr_threshold: the multiple of moving std to triger signals
#     :returns: the expected up/down rate to triger signals
#     :raises: none
#     """
#     x = sympy.Symbol('x')
#
#     df = np.hstack((df.tail(n - 1)[rate_col].values, x))
#     ma = df.mean()
#     std = sympy.sqrt(sum((df - ma) ** 2) / (n - 1))
#     result = sympy.solve(((x - ma) ** 2) - ((mr_threshold * std) ** 2), x)
#
#     return result


# Bollinger Band
def add_bb_features(df, n=20, ndev=2, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Bollinger Band

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ndev: standard deviation factor
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate bollinger band
    mavg = sm(series=df[close], periods=n).mean()
    mstd = sm(series=df[close], periods=n).std(ddof=0)
    high_band = mavg + ndev * mstd
    low_band = mavg - ndev * mstd

    # fill na values
    if fillna:
        mavg = mavg.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        mstd = mstd.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        high_band = high_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        low_band = low_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')

    # assign values to df
    df['mavg'] = mavg
    df['mstd'] = mstd
    df['bb_high_band'] = high_band
    df['bb_low_band'] = low_band

    if cal_signal:
        df['bb_signal'] = 'n'
        df['bb_trend'] = 'n'
        buy_idx = df.query(f'{close} < bb_low_band').index
        sell_idx = df.query(f'{close} > bb_high_band').index
        df.loc[buy_idx, 'bb_trend'] = 'u'
        df.loc[sell_idx, 'bb_trend'] = 'd'

    return df


# Donchian Channel
def add_dc_features(df, n=20, ohlcv_col=default_ohlcv_col, fillna=False, cal_signal=True):
    """
    Calculate Donchian Channel

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    # high = ohlcv_col['high']
    # low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate dochian channel
    high_band = df[close].rolling(n, min_periods=0).max()
    low_band = df[close].rolling(n, min_periods=0).min()
    middle_band = (high_band + low_band) / 2

    # fill na values
    if fillna:
        high_band = high_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        low_band = low_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        middle_band = middle_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')

    # assign values to df
    df['dc_high_band'] = high_band
    df['dc_low_band'] = low_band
    df['dc_middle_band'] = middle_band

    # calculate signals
    if cal_signal:
        df['dc_signal'] = 'n'
        buy_idx = df.query(f'{close} <= dc_low_band').index
        sell_idx = df.query(f'{close} >= dc_high_band').index
        df.loc[buy_idx, 'dc_signal'] = 'b'
        df.loc[sell_idx, 'dc_signal'] = 's'

    return df


# Keltner channel (KC)
def add_kc_features(df, n=10, ohlcv_col=default_ohlcv_col, method='atr', fillna=False, cal_signal=True):
    """
    Calculate Keltner channel (KC)

    :param df: original OHLCV dataframe
    :param n: look back window size
    :param ohlcv_col: column name of Open/High/Low/Close/Volume
    :param method: 'atr' or 'ta'
    :param fillna: whether to fill na with 0
    :param cal_signal: whether to calculate signal
    :returns: dataframe with new features generated
    """
    # copy dataframe
    df = df.copy()

    # set column names
    # open = ohlcv_col['open']
    high = ohlcv_col['high']
    low = ohlcv_col['low']
    close = ohlcv_col['close']
    # volume = ohlcv_col['volume']

    # calculate keltner channel
    typical_price = (df[high] + df[low] + df[close]) / 3.0
    middle_band = typical_price.rolling(n, min_periods=0).mean()

    if method == 'atr':
        df = add_atr_features(df=df)
        high_band = middle_band + 2 * df['atr']
        low_band = middle_band - 2 * df['atr']

    else:
        typical_price = ((4 * df[high]) - (2 * df[low]) + df[close]) / 3.0
        high_band = typical_price.rolling(n, min_periods=0).mean()

        typical_price = ((-2 * df[high]) + (4 * df[low]) + df[close]) / 3.0
        low_band = typical_price.rolling(n, min_periods=0).mean()

    # fill na values
    if fillna:
        middle_band = middle_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        high_band = high_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')
        low_band = low_band.replace([np.inf, -np.inf], np.nan).fillna(method='backfill')

    # assign values to df
    df['kc_high_band'] = high_band
    df['kc_middle_band'] = middle_band
    df['kc_low_band'] = low_band

    # calculate signals
    if cal_signal:
        df['kc_signal'] = 'n'
        buy_idx = df.query(f'{close} < kc_low_band').index
        sell_idx = df.query(f'{close} > kc_high_band').index
        df.loc[buy_idx, 'kc_signal'] = 'b'
        df.loc[sell_idx, 'kc_signal'] = 's'

    return df


# bcutils.js

def remove_duplicated_index(df, keep='first'):
    """
    remove duplicated index with its row from dataframe

    :param df: dataframe
    :param keep: first or last duplicated index to keep
    :returns: dataframe without duplicated index
    :raises: Exception
    """
    try:
        df = df[~df.index.duplicated(keep=keep)].copy()
    except Exception as e:
        print(e)

    return df


# ----------------------- Dataframe manipulation ------------------#
def df_2_timeseries(df, time_col='date'):
    """
    Convert dataframe to timeseries-dataframe

    :param df: dataframe
    :param time_col: the column in the dataframe which contains time information
    :returns: timeseries dataframe with time_col as index
    :raises: none
    """
    df = df.set_index(time_col)
    df.index = pd.DatetimeIndex(df.index)

    return df
