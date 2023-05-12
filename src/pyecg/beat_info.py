import numpy as np
from scipy import stats
from scipy.fft import rfft, rfftfreq
from pyecg.extra.pqrst import PQRST
import types


class BeatInfo:
    """
    Provides information and features for a single beat.

    Parameters
    ----------
    beat_loc : int
        Index of beat in the rpeaks locations list, considering pre-RR and post-RR values.
    fs : int, optional
        Sampling rate, by default 360
    in_ms : bool, optional
        Whether to calculate rr-intervals in time(miliseconds) or samples, by default True

    Attributes
    ----------
    beat_loc : int
        Index of beat in the rpeaks locations list, considering pre-RR and post-RR values.
    fs : int, optional
        Sampling rate, by default 360
    in_ms : bool, optional
        Whether to calculate rr-intervals in time(miliseconds) or samples, by default True
    whole_waveform : list
        Whole waveform.
    bwaveform : list
        Trimmed beat waveform. Selected as a segment of the whole provided waveform.
    start_idx: int
        The index of the first sample of the waveform according to the original signal.
    rri : list
        RR intervals in ms if in_ms=True.
    rri_smpl : list
        RR intervals in samples.
    sdrri : list
        Successive RRI differences.
    avail_features : list
        List of fetaure names (strings) that already have a definition in the class.
    features : dict
        Dictionary with keys(strings) equal to feature names and dict values
        equal to features values.
    """

    def __init__(self, beat_loc, fs=360, in_ms=True):
        self.fs = fs
        self.beat_loc = beat_loc
        self.in_ms = in_ms

    def __call__(self, data):
        """
        Parameters
        ----------
        data : dict
            A dict containing data about the beat with keys:

            'waveform' : list
                Waveform of the beat.
            'rpeak_locs' : list
                A list containing locations of rpeaks.
            'rec_id' : int
                Record id of the original signal which the excerpt is extracted from.
            'start_idx' : int
                Index of beginnig of the segmented waveform in the original signal.
            'label' : str
                Type of the beat.
        """

        self.data = data
        self.label = data["label"]
        self.rpeaks = data["rpeak_locs"]
        self.whole_waveform = data["waveform"]  # Whole waveform
        self.rri = self.get_rris(in_ms=self.in_ms)
        self.rri_smpl = self.get_rris(in_ms=False)
        self.sdrri = self.get_sdrri()
        self.bwaveform, self.wfpts = self.get_beat_waveform()  # beat waveform
        self.avail_features = self.available_features()
        self.features = self.compute_features()
        if self.bwaveform is not None:
            self.pqrst_dict = self.pqrst()
        if self.label == "V":
            pass
            # self.plot_wf() #plot for debug

    def available_features(self):
        """Returns availble features that can be computed.

        Returns
        -------
        list
            List containing features names as strings.
        """
        avail_feats = [f for f in dir(self) if f.startswith("F_")]
        return avail_feats

    def add_features(self, new_features):
        """Adds new features.

        Parameters
        ----------
        new_features : list
            Names of new features. Such as: [new_feature_1, new_feature_2]
        """
        for new_feature in new_features:
            setattr(self, new_feature.__name__, types.MethodType(new_feature, self))

    def select_features(self, features):
        """Select features.

        Parameters
        ----------
        features : list
            List of feature names(strings).
        """
        self.selected_features_names = features

    def compute_features(self):
        """Computes features.

        Returns
        -------
        dict
            Dictionary with keys(strings) equal to feature names and dict values
            equal to features values.
        """
        if (
            hasattr(self, "selected_features_names")
            and len(self.selected_features_names) > 0
        ):
            features_names = self.selected_features_names
        else:
            features_names = self.avail_features
        feature_dict = {}
        for f in features_names:
            ret = getattr(self, f)()
            # if the feature function returns one value
            if not isinstance(ret, dict):
                feature_dict[f] = ret
            # if the feature function returns multiple values as a dict
            elif isinstance(ret, dict):
                feature_dict.update(ret)
        return feature_dict

    def get_beat_waveform(self, win=[-0.35, 0.65]):
        """Segment beat waveform according to the pre and post rri intervals."""
        try:
            beat_rpeak_idx = self.rpeaks[self.beat_loc]
            prerri = self.rri_smpl[self.beat_loc - 1]
            postrri = self.rri_smpl[self.beat_loc]
            beat_onset_org = int(beat_rpeak_idx + win[0] * prerri)
            beat_offset_org = int(beat_rpeak_idx + win[1] * postrri)

            beat_onset = beat_onset_org - self.data["start_idx"]
            beat_offset = beat_offset_org - self.data["start_idx"]
            if beat_onset < 0:
                beat_onset = 0
            if beat_offset > len(self.whole_waveform):
                beat_offset = len(self.whole_waveform) - 1
            rpk = beat_rpeak_idx - self.data["start_idx"]
            bwaveform = self.whole_waveform[beat_onset:beat_offset]
            bwaveform = np.asarray(bwaveform)
            # if len(bwaveform)==0 or beat_onset*beat_offset<0:
            # print(len(self.whole_waveform))
            # print([beat_onset_org,beat_offset_org])
            # print(beat_rpeak_idx)
            # print(self.start_idx)
            # print([beat_onset,beat_offset])
            assert len(bwaveform) > 0, "beat waveform length cannot be zero!"

            wfpts = {
                "beat_onset_org": beat_onset_org,
                "beat_offset_org": beat_offset_org,
                "beat_onset": beat_onset,
                "beat_offset": beat_offset,
                "rpk": rpk,
            }
            return bwaveform, wfpts
        except Exception as e:
            import traceback

            traceback.print_exc()
            return None, None
            print("waveform error!")
            print(
                "rec_id={}, sindex={}".format(
                    self.data["rec_id"], self.data["start_idx"]
                )
            )
            import matplotlib.pyplot as plt

            plt.plot(self.whole_waveform)
            plt.plot(bwaveform)
            plt.scatter(beat_onset, self.whole_waveform[beat_onset], color="yellow")
            plt.scatter(beat_offset, self.whole_waveform[beat_offset], color="orange")
            plt.scatter(rpk, self.whole_waveform[rpk], color="r")

    def get_rris(self, in_ms):
        """Compute RR intervals.

        Parameters
        ----------
        in_ms : bool
            If True will be in time(miliseconds). If False will be in samples.

        Returns
        -------
        list
            Contains RR intervals.
        """
        if in_ms:
            rpeaks = [1000 * item / self.fs for item in self.rpeaks]
        else:
            rpeaks = self.rpeaks
        rri = [rpeaks[i] - rpeaks[i - 1] for i in range(1, len(rpeaks))]
        return rri

    def get_sdrri(self):
        """Computes successive differences of rri.

        Returns
        -------
        list
            Contains successive differences of rri.
        """
        sdrri = list(np.diff(np.asarray(self.rri)))
        return sdrri

    # ============================================================
    # RRI features
    # ============================================================
    def F_post_rri(self):
        return self.rri[self.beat_loc]

    def F_pre_rri(self):
        return self.rri[self.beat_loc - 1]

    def F_ratio_post_pre(self):
        post = self.F_post_rri()
        pre = self.F_pre_rri()
        return post / pre

    def F_diff_post_pre(self):
        post = self.F_post_rri()
        pre = self.F_pre_rri()
        return post - pre

    def F_diff_post_pre_nr(self):
        post = self.F_post_rri()
        pre = self.F_pre_rri()
        return (post - pre) / self.F_rms_rri()

    def F_median_rri(self):
        # median of rri
        return np.median(self.rri)

    def F_mean_pre_rri(self):
        # average of pre-rri
        pre_rri = self.rri[: self.beat_loc]
        return np.mean(pre_rri)

    def F_rms_rri(self):
        # rms of rri
        rri = np.asarray(self.rri)
        rms = np.sqrt(np.mean(rri**2))
        return rms

    def F_std_rri(self):
        # std of rr intervals
        return np.std(self.rri)

    def F_ratio_pre_rms(self):
        # ratio of pre-rr interval to rms
        return self.F_pre_rri() / self.F_rms_rri()

    def F_ratio_post_rms(self):
        # ratio of post-rr interval to rms
        return self.F_post_rri() / self.F_rms_rri()

    def F_diff_pre_avg_nr(self):
        # diff of pre-rr interval to local rr average
        return (self.F_pre_rri() - self.F_median_rri()) / self.F_rms_rri()

    def F_diff_post_avg_nr(self):
        # diff of post-rr interval to local rr average
        return (self.F_post_rri() - self.F_median_rri()) / self.F_rms_rri()

    def F_compensate_ratio(self):
        postpre = self.F_post_rri() + self.F_pre_rri()
        _2t2ndpre = 2 * self.rri[self.beat_loc - 2]  # 2 times second pre rri
        return postpre / _2t2ndpre

    def F_compensate_diff_nr(self):
        postpre = self.F_post_rri() + self.F_pre_rri()
        _2t2ndpre = 2 * self.rri[self.beat_loc - 2]  # 2 times second pre rri
        return (postpre - _2t2ndpre) / self.F_rms_rri()

    def F_heart_rate(self):
        pre_rri = (
            self.rpeaks[self.beat_loc] - self.rpeaks[self.beat_loc - 1]
        ) / self.fs
        hr = 60 / pre_rri
        return hr

    # ============================================================
    # SDRRI features
    # ============================================================
    def F_post_sdrri(self):
        try:
            return self.sdrri[self.beat_loc]
        except:
            return None

    def F_onbeat_sdrri(self):
        # on beat(postrri-prerri)
        return self.sdrri[self.beat_loc - 1]

    def F_pre_sdrri(self):
        # pre beat
        return self.sdrri[self.beat_loc - 2]

    def F_mean_sdrri(self):
        # average of sdrri
        return np.mean(self.sdrri)

    def F_absmean_sdrri(self):
        # abs average of sdrri
        return np.mean(np.abs(self.sdrri))

    def F_mean_pre_sdrri(self):
        # average of pre-rri
        pre_sdrri = self.sdrri[: self.beat_loc - 1]
        return np.mean(pre_sdrri)

    def F_rms_sdrri(self):
        # rms of rri
        sdrri = np.asarray(self.sdrri)
        rms = np.sqrt(np.mean(sdrri**2))
        return rms

    def F_std_sdrri(self):
        # std of sdrri
        return np.std(self.sdrri)

    # ============================================================
    # Waveform features
    # ============================================================
    def reported_rpeak(self):
        return self.rpeaks[self.beat_loc] - self.wfpts["beat_onset_org"]

    def F_beat_max(self):
        return max(self.bwaveform)

    def F_beat_min(self):
        return min(self.bwaveform)

    def F_maxmin_diff(self):
        return self.F_beat_max() - self.F_beat_min()

    def F_maxmin_diff_norm(self):
        return self.F_maxmin_diff() / self.F_beat_rms()

    def F_beat_mean(self):
        return np.mean(self.bwaveform)

    def F_beat_std(self):
        return np.std(self.bwaveform)

    def F_beat_skewness(self):
        return stats.skew(self.bwaveform)

    def F_beat_kurtosis(self):
        return stats.kurtosis(self.bwaveform)

    def F_beat_rms(self):
        rms = np.sqrt(np.mean(self.bwaveform**2))
        return rms

    def pqrst(self):
        # 120ms <Normal_PR< 220ms.
        # 75ms  <Normal_QRS< 120ms
        # QRS region estimate 160ms.
        # Compute: QRS width,Q,R,S amplitudes.

        beat_pqrst = PQRST()
        beat_pqrst(self.bwaveform)
        p = beat_pqrst.pwave
        q = beat_pqrst.qwave
        r = beat_pqrst.rwave
        s = beat_pqrst.swave
        pr = beat_pqrst.pr_interval
        qs = beat_pqrst.qs_interval
        return {"p": p, "q": q, "r": r, "s": s, "pr": pr, "qs": qs}

    def pqrst_segs(self):
        # splits the beat waveform into 3-segments using q and s points in the middle
        pqrst = self.pqrst_dict
        points = [0, pqrst["q"][0], pqrst["s"][0], len(self.bwaveform)]

        lmax = []
        lmin = []
        lmean = []
        lmedian = []
        std = []
        lskewness = []
        lkurtosis = []
        lrms = []

        try:
            for i in range(3):
                s_ix = int(points[i])
                e_ix = int(points[i + 1])
                seg = self.bwaveform[s_ix:e_ix]
                lmax.append(max(seg))
                lmin.append(min(seg))
                lmean.append(np.mean(seg))
                lmedian.append(np.median(seg))
                std.append(np.std(seg))
                lskewness.append(stats.skew(seg))
                lkurtosis.append(stats.kurtosis(seg))
                lrms.append(np.sqrt(np.mean(seg**2)))

            res = [lmax, lmin, lmean, lmedian, std, lskewness, lkurtosis, lrms]

            # agg results
            mean_res = []
            std_res = []
            rms_res = []
            for mtrc in res:
                mtrc = np.asarray(mtrc)
                mean_res.append(np.mean(mtrc))
                std_res.append(np.std(mtrc))
                rms_res.append(np.sqrt(np.mean(mtrc**2)))

            aggs = [mean_res, std_res, rms_res]
            return res, aggs
        except ValueError:
            # print('pqrst segs error!')
            # print('rec_id={}, sindex={}'.format(
            # 					self.data['rec_id'],
            # 					self.data['start_idx']))
            res = [[np.nan] * 3] * 8
            aggs = [[np.nan] * 8] * 3
            return res, aggs

    def pr_interval(self):
        # pr interval in ms
        pr = self.pqrst_dict["pr"]
        return pr

    def qs_interval(self):
        # qs interval in ms
        qs = self.pqrst_dict["qs"]
        return qs

    def qs_interval_nr(self):
        # qs interval (normalized)
        qs = self.pqrst_dict["qs"]
        return qs / self.rms_rri()

    def pflag(self):
        if self.label == "N":
            return 1
        else:
            return 0

    def nsampels(self, n_samples=50):
        # get samples of the waveform
        dt = int(len(self.bwaveform) / n_samples)
        samples = []
        for i in range(n_samples):
            samples.append(self.bwaveform[int(i * dt)])
        return samples

    def sub_segs(self, n_subsegs=10):
        # splits the beat waveform into sub-segments of equal length
        lmax = []
        lmin = []
        lmean = []
        lmedian = []
        std = []
        lskewness = []
        lkurtosis = []
        lrms = []

        for i in range(n_subsegs):
            s_ix = int(i / n_subsegs * len(self.bwaveform))
            e_ix = int((i + 1) / n_subsegs * len(self.bwaveform))
            seg = self.bwaveform[s_ix:e_ix]
            lmax.append(max(seg))
            lmin.append(min(seg))
            lmean.append(np.mean(seg))
            lmedian.append(np.median(seg))
            std.append(np.std(seg))
            lskewness.append(stats.skew(seg))
            lkurtosis.append(stats.kurtosis(seg))
            lrms.append(np.sqrt(np.mean(seg**2)))

        res = [lmax, lmin, lmean, lmedian, std, lskewness, lkurtosis, lrms]

        # agg results
        mean_res = []
        std_res = []
        rms_res = []
        for mtrc in res:
            mtrc = np.asarray(mtrc)
            mean_res.append(np.mean(mtrc))
            std_res.append(np.std(mtrc))
            rms_res.append(np.sqrt(np.mean(mtrc**2)))

        aggs = [mean_res, std_res, rms_res]
        return res, aggs

    # ============================================================
    # Spectral features of the beat waveform
    # ============================================================
    def fft_features(self):
        # return fft of each beat bwaveform as a list.
        sig = self.bwaveform
        num_samples = sig.size
        # xf = rfftfreq(num_samples, 1 / self.fs)
        yf = np.abs(rfft(sig))

        return list(yf)

    # ============================================================
    # helper functions
    # ============================================================
    def plot_wf(self):
        from matplotlib import figure

        # fig = figure.Figure()
        fig = figure.Figure(figsize=(8, 4), dpi=170)
        ax = fig.add_subplot(111)
        ax.plot(self.whole_waveform)
        # plt.plot(bwaveform)
        beat_rpeak_idx = self.rpeaks[self.beat_loc]
        beat_onset = self.wfpts["beat_onset"]
        beat_offset = self.wfpts["beat_offset"]
        ax.scatter(
            beat_onset,
            self.whole_waveform[beat_onset],
            color="deeppink",
            marker=">",
            s=40,
        )
        ax.scatter(
            beat_offset,
            self.whole_waveform[beat_offset],
            color="deeppink",
            marker="<",
            s=40,
        )
        rpk = beat_rpeak_idx - self.data["start_idx"]
        ax.scatter(rpk, self.whole_waveform[rpk], color="red")
        try:
            p = (self.pqrst_dict["p"][0]) + beat_onset
            q = (self.pqrst_dict["q"][0]) + beat_onset
            r = (self.pqrst_dict["r"][0]) + beat_onset
            s = (self.pqrst_dict["s"][0]) + beat_onset
            ax.scatter(p, self.whole_waveform[p], color="cyan")
            ax.scatter(q, self.whole_waveform[q], color="magenta")
            ax.scatter(r, self.whole_waveform[r], color="violet", marker="x")
            ax.scatter(s, self.whole_waveform[s], color="lime")
        except:
            pass
        ax.set_title(self.label)
        ax.set_ylim(-1, 2)
        ptnt = str(self.data["rec_id"])
        fldr = "../wvplots/{}".format(ptnt)
        try:
            import os

            os.makedirs(fldr, exist_ok=True)
        except OSError as err:
            print("Folder can not be created!")
        fig.savefig(
            "{}/{}_{}_{}.jpg".format(
                fldr, ptnt, str(self.data["start_idx"]), self.label
            )
        )
        fig.clear()
